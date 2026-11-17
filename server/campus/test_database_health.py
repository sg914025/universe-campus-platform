"""Database constraint, integrity, backup and permission regressions. Author: UniVerse Team."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import date
from io import StringIO
import json
import sqlite3
import uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import SimpleTestCase, TestCase, Client, override_settings
from django.urls import reverse

from accounts.models import Profile
from 帖子.models import profile
from 跑腿.models import task, wallet_record
from .models import Venue, VenueBooking, VenueWaitlist, SecurityBackup, DatabaseInspection, StaffAuditEvent
from .database_health import inspect_database
from .security_service import create_backup, verify_backup, rehearse_backup, backup_path, digest


class SQLiteDiagnosticsTests(SimpleTestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'source.sqlite3'
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript('CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(id INTEGER PRIMARY KEY,parent_id INTEGER REFERENCES parent(id)); INSERT INTO parent VALUES(1); INSERT INTO child VALUES(1,1);')

    def test_full_check_is_read_only_and_contains_no_contents_or_path(self):
        before=digest(self.path)
        report=inspect_database(self.path,full=True)
        self.assertTrue(report['healthy']);self.assertEqual(report['foreign_key_errors'],0)
        self.assertEqual(report['table_count'],2);self.assertEqual(len(report['tables']),2)
        self.assertEqual(digest(self.path),before);self.assertNotIn(str(self.path),str(report))

    def test_foreign_key_violation_is_detected_even_when_integrity_check_passes(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('INSERT INTO child VALUES(2,999)');db.commit()
        report=inspect_database(self.path,full=True)
        self.assertTrue(report['integrity_ok']);self.assertFalse(report['healthy'])
        self.assertEqual(report['foreign_key_errors'],1)

    def test_missing_and_invalid_database_are_not_created_or_reported_healthy(self):
        missing=self.path.with_name('missing.sqlite3')
        self.assertFalse(inspect_database(missing)['healthy']);self.assertFalse(missing.exists())
        self.path.write_text('SECRET_INVALID_CONTENT',encoding='utf-8')
        report=inspect_database(self.path);self.assertFalse(report['completed'])
        self.assertNotIn('SECRET_',str(report))

    def test_timeout_is_not_a_pass(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.executemany('INSERT INTO parent VALUES(?)',[(n,) for n in range(2,3000)]);db.commit()
        report=inspect_database(self.path,full=True,timeout=-1)
        self.assertFalse(report['healthy']);self.assertFalse(report['completed'])

    def test_wal_allows_read_snapshot_while_another_connection_commits(self):
        with closing(sqlite3.connect(self.path)) as reader,closing(sqlite3.connect(self.path,timeout=.1)) as writer:
            reader.execute('PRAGMA journal_mode=WAL');reader.execute('BEGIN')
            self.assertEqual(reader.execute('SELECT count(*) FROM parent').fetchone()[0],1)
            writer.execute('INSERT INTO parent VALUES(2)');writer.commit()
            self.assertEqual(reader.execute('SELECT count(*) FROM parent').fetchone()[0],1)
            reader.rollback()
            self.assertEqual(reader.execute('SELECT count(*) FROM parent').fetchone()[0],2)


class DatabaseConstraintsTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('db-fixture')
        self.other=get_user_model().objects.create_user('db-other')
        self.venue=Venue.objects.create(name='test seat',kind='study')

    def rejected(self,operation):
        with self.assertRaises(IntegrityError),transaction.atomic():operation()

    def test_student_number_unique_but_legacy_blank_numbers_are_allowed(self):
        first=Profile.objects.create(user=self.user,full_name='Fixture',gender='other')
        second=Profile.objects.create(user=self.other,full_name='Fixture',gender='other')
        first.student_number='209912345';first.save()
        self.rejected(lambda:Profile.objects.filter(pk=second.pk).update(student_number=first.student_number))
        self.rejected(lambda:Profile.objects.filter(pk=first.pk).update(age=121))

    def test_wallet_cannot_be_negative_or_overflow_even_with_bulk_update(self):
        row,_=profile.objects.get_or_create(user=self.user)
        for amount in (-1,10000000000):
            self.rejected(lambda:profile.objects.filter(pk=row.pk).update(balance=amount))
        row.refresh_from_db();self.assertEqual(row.balance,0)

    def test_booking_status_and_time_slot_are_enforced_in_database(self):
        row=VenueBooking.objects.create(user=self.user,venue=self.venue,day=date(2099,1,1),slot='08',request_key=uuid.uuid4())
        self.rejected(lambda:VenueBooking.objects.filter(pk=row.pk).update(slot='09'))
        self.rejected(lambda:VenueBooking.objects.filter(pk=row.pk).update(status='unknown'))
        self.rejected(lambda:VenueBooking.objects.create(user=self.other,venue=self.venue,day=row.day,slot='08',request_key=uuid.uuid4()))

    def test_waitlist_and_floor_constraints(self):
        row=VenueWaitlist.objects.create(user=self.user,venue=self.venue,day=date(2099,1,1),slot='08')
        self.rejected(lambda:VenueWaitlist.objects.filter(pk=row.pk).update(status='unknown'))
        self.rejected(lambda:VenueWaitlist.objects.filter(pk=row.pk).update(slot='09'))
        self.rejected(lambda:Venue.objects.filter(pk=self.venue.pk).update(floor=21))
        self.rejected(lambda:Venue.objects.filter(pk=self.venue.pk).update(floor=0))

    def test_errand_amounts_are_protected(self):
        row=task.objects.create(owner=self.user,title='fixture',description='fixture',address='fixture',phone='fixture',price=5)
        self.rejected(lambda:task.objects.filter(pk=row.pk).update(price=-1))
        self.rejected(lambda:wallet_record.objects.create(user=self.user,task=row,kind='payment',amount=-1))

    def test_attendance_query_uses_due_index(self):
        with connection.cursor() as cur:
            cur.execute("EXPLAIN QUERY PLAN SELECT id FROM campus_venuebooking WHERE status='reserved' AND checked_in_at IS NULL AND checkin_deadline<'2099-01-01'")
            self.assertIn('booking_checkin_due',str(cur.fetchall()))


class DatabaseMaintenanceCommandTests(SimpleTestCase):
    def test_wal_refusal_reports_actual_mode_and_nonzero_result(self):
        output=StringIO()
        with patch('campus.management.commands.database_maintenance.connection') as db, \
             patch('campus.management.commands.database_maintenance.database_path'):
            db.vendor='sqlite';db.in_atomic_block=False
            db.cursor.return_value.__enter__.return_value.fetchone.return_value=('delete',)
            with self.assertRaises(CommandError):
                call_command('database_maintenance','wal',stdout=output)
        self.assertEqual(json.loads(output.getvalue()),{'healthy':False,'journal_mode':'delete'})

    def test_django_database_error_has_safe_command_message(self):
        with patch('campus.management.commands.database_maintenance.connection') as db, \
             patch('campus.management.commands.database_maintenance.database_path'):
            db.vendor='sqlite';db.in_atomic_block=False
            db.cursor.side_effect=DatabaseError('PRIVATE_DATABASE_DETAILS')
            with self.assertRaises(CommandError) as error:
                call_command('database_maintenance','optimize',stdout=StringIO())
        self.assertNotIn('PRIVATE_',str(error.exception))
        self.assertIn('Database operation failed',str(error.exception))


class RestoreAndAdminTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.source=self.base/'live.sqlite3'
        with closing(sqlite3.connect(self.source)) as db:
            db.executescript('CREATE TABLE fixture(id INTEGER PRIMARY KEY, value TEXT); INSERT INTO fixture VALUES(1,"PRIVATE_TEXT");')
        setting=override_settings(BASE_DIR=self.base);setting.enable();self.addCleanup(setting.disable)
        self.root=get_user_model().objects.create_user('db-root',is_superuser=True,is_staff=True)
        self.user=get_user_model().objects.create_user('db-ordinary')

    def backup(self):
        with patch('campus.security_service.database_path',return_value=self.source):return create_backup(self.root)

    def test_restore_rehearses_without_changing_live_data_and_cleans_copy(self):
        row=self.backup();before=digest(self.source)
        report=rehearse_backup(row);row.refresh_from_db()
        self.assertTrue(report['healthy']);self.assertEqual(row.restore_status,'passed')
        self.assertEqual(report['table_count'],1);self.assertEqual(digest(self.source),before)
        self.assertEqual(list((self.base/'runtime/security_backups').glob('restore-*')),[])
        self.assertNotIn('PRIVATE_TEXT',str(row.restore_report))

    def test_corrupt_backup_fails_rehearsal(self):
        row=self.backup();backup_path(row).write_bytes(b'corrupt')
        self.assertFalse(rehearse_backup(row)['healthy']);row.refresh_from_db()
        self.assertEqual(row.status,'failed');self.assertEqual(row.restore_status,'failed')

    def test_failed_cli_copy_replaces_previous_pass_and_cleans_partial(self):
        row=self.backup();before=digest(self.source)
        self.assertTrue(rehearse_backup(row)['healthy'])
        previous=row.restored_at
        def interrupted_copy(source,target):
            Path(target).write_bytes(b'partial restore')
            raise OSError('PRIVATE_FILESYSTEM_DETAILS')
        output=StringIO()
        with patch('campus.security_service.shutil.copyfile',side_effect=interrupted_copy):
            with self.assertRaises(CommandError):
                call_command('database_maintenance','rehearse',backup_id=row.pk,stdout=output)
        row.refresh_from_db()
        self.assertEqual(row.restore_status,'failed');self.assertEqual(row.status,'verified')
        self.assertGreaterEqual(row.restored_at,previous)
        self.assertEqual(row.restore_report,{'healthy':False,'error':'rehearsal_incomplete'})
        self.assertEqual(json.loads(output.getvalue()),row.restore_report)
        self.assertEqual(list((self.base/'runtime/security_backups').glob('restore-*')),[])
        self.assertEqual(digest(self.source),before);self.assertTrue(verify_backup(row))

    def test_partial_backup_is_removed_on_validation_failure(self):
        with patch('campus.security_service.inspect_database',return_value={'healthy':False}):
            with self.assertRaises(ValueError):self.backup()
        self.assertEqual(SecurityBackup.objects.count(),0)
        self.assertEqual(list((self.base/'runtime/security_backups').iterdir()),[])

    def test_wal_backup_includes_committed_rows_and_needs_no_sidecar(self):
        with closing(sqlite3.connect(self.source)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('INSERT INTO fixture VALUES(2,"NEW_PRIVATE_TEXT")');writer.commit()
            row=self.backup()
        self.assertTrue(verify_backup(row))
        with closing(sqlite3.connect(backup_path(row))) as restored:
            self.assertEqual(restored.execute('SELECT count(*) FROM fixture').fetchone()[0],2)
            self.assertEqual(restored.execute('PRAGMA journal_mode').fetchone()[0],'delete')

    def test_admin_actions_require_superadmin_post_and_csrf(self):
        row=self.backup()
        urls=[reverse('security-database-inspect'),reverse('security-rehearse',args=[row.pk])]
        for url in urls:
            self.client.force_login(self.user);self.assertEqual(self.client.post(url).status_code,403)
            self.client.force_login(self.root);self.assertEqual(self.client.get(url).status_code,405)
            csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.root)
            self.assertEqual(csrf.post(url).status_code,403)

    def test_admin_can_record_check_and_view_it(self):
        self.client.force_login(self.root)
        with patch('campus.security_service.database_path',return_value=self.source):
            response=self.client.post(reverse('security-database-inspect'))
        self.assertEqual(response.status_code,302);self.assertTrue(DatabaseInspection.objects.get().healthy)
        self.assertTrue(StaffAuditEvent.objects.filter(action='执行数据库完整检查').exists())
        response=self.client.get(reverse('security-database'))
        self.assertContains(response,'数据库健康检查');self.assertContains(response,'检查通过')
        self.assertNotContains(response,'PRIVATE_TEXT');self.assertNotContains(response,str(self.source))
