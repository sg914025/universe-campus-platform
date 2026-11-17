"""Explicit database maintenance; no destructive restore. Author: UniVerse Team."""
import json
import sqlite3
from uuid import UUID
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, DatabaseError
from campus.database_health import inspect_database, record_inspection
from campus.security_service import database_path, create_backup, rehearse_backup
from campus.models import SecurityBackup


class Command(BaseCommand):
    help = 'Check SQLite; create/verify a backup; rehearse in isolation; explicitly enable WAL or optimize indexes.'

    def add_arguments(self, parser):
        parser.add_argument('action', choices=['check','backup','rehearse','wal','optimize'])
        parser.add_argument('--backup-id', type=UUID)
        parser.add_argument('--full', action='store_true')
        parser.add_argument('--record', action='store_true', help='Store a full check in the superadmin database page.')

    def handle(self, *args, **options):
        try:
            action=options['action']
            if action=='check':
                report=record_inspection().report if options['record'] else inspect_database(database_path(), full=options['full'])
            elif action=='backup':
                row=create_backup(None)
                report={'healthy':True,'backup_id':str(row.pk),'size':row.size,'sha256':row.digest}
            elif action=='rehearse':
                if not options['backup_id']:raise CommandError('Use --backup-id with a managed backup UUID.')
                row=SecurityBackup.objects.get(pk=options['backup_id'])
                report=rehearse_backup(row)
            else:
                if connection.vendor!='sqlite' or connection.in_atomic_block:
                    raise CommandError('SQLite maintenance requires an autocommit connection.')
                database_path()  # Refuse memory databases and missing files.
                with connection.cursor() as cur:
                    if action=='wal':
                        cur.execute('PRAGMA journal_mode=WAL')
                        mode=cur.fetchone()[0].lower()
                        report={'healthy':mode=='wal','journal_mode':mode}
                    else:
                        cur.execute('PRAGMA optimize')
                        report={'healthy':True,'optimized':True}
            self.stdout.write(json.dumps(report,ensure_ascii=False))
            if not report['healthy']:raise CommandError('Database operation did not pass; see the aggregate report above.')
        except (OSError,ValueError,sqlite3.Error,DatabaseError,SecurityBackup.DoesNotExist) as error:
            raise CommandError('Database operation failed. Check database availability and the managed backup ID.') from error
