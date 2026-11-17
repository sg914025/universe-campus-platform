import json,sqlite3,tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth import get_user_model,authenticate
from django.test import TestCase,SimpleTestCase,RequestFactory,Client,override_settings
from django.urls import reverse
from .models import SecurityScan,SecurityFinding,SecurityEvent,SecurityBackup
from .security_service import calculate,run_scan,create_backup,verify_backup,backup_path,collect

CHECKS=[dict(code='test',title='示例检查',status='warn',evidence='配置需关注',recommendation='复查',weight=10,group='configuration',severity='medium')]

class ScoreTests(SimpleTestCase):
    def test_unknown_never_counts_as_a_pass(self):
        score,coverage=calculate([{'status':'pass','weight':10},{'status':'fail','weight':10},{'status':'unknown','weight':90}])
        self.assertEqual((score,coverage),(50,67))
        self.assertEqual(calculate([{'status':'unknown','weight':10}]),(0,0))
    def test_warning_is_half_weight(self):self.assertEqual(calculate([{'status':'warn','weight':10}]),(50,100))

class SecurityCenterTests(TestCase):
    def setUp(self):
        self.root=get_user_model().objects.create_user('security_test_root',is_superuser=True,is_staff=True)
        self.user=get_user_model().objects.create_user('security_test_user')
        self.client.force_login(self.root)
    def test_all_five_pages_superadmin_only(self):
        for section in ['overview','twin','risks','database','daily']:
            url=reverse('security-'+section)
            self.assertEqual(self.client.get(url).status_code,200)
            self.client.force_login(self.user);self.assertEqual(self.client.get(url).status_code,403)
            self.client.force_login(self.root)
    def test_ordinary_staff_cannot_access_actions(self):
        self.user.is_staff=True;self.user.save();self.client.force_login(self.user)
        for name in ['security-check','security-backup']:self.assertEqual(self.client.post(reverse(name)).status_code,403)
    def test_scan_actions_require_post_and_csrf(self):
        self.assertEqual(self.client.get(reverse('security-check')).status_code,405)
        client=Client(enforce_csrf_checks=True);client.force_login(self.root)
        self.assertEqual(client.post(reverse('security-check')).status_code,403)
    def test_staff_login_keeps_security_destination(self):
        from .management_views import destination
        req=RequestFactory().get('/management/login/superadmin/',{'next':'/management/security/twin/'},HTTP_HOST='testserver')
        self.assertEqual(destination(req,'superadmin'),'/management/security/twin/')
    @patch('campus.security_service.collect',return_value=(CHECKS,{}))
    def test_daily_reuses_actual_snapshot(self,mock):
        first=run_scan(self.root,True);second=run_scan(self.root,True)
        self.assertEqual(first.pk,second.pk);self.assertEqual(mock.call_count,1)
        self.assertEqual(SecurityScan.objects.count(),1)
    def test_risk_only_resolves_after_passing_recheck(self):
        with patch('campus.security_service.collect',return_value=(CHECKS,{})):run_scan(self.root)
        issue=SecurityFinding.objects.get();self.client.post(reverse('security-track',args=[issue.pk]),{'note':'正在处理'})
        issue.refresh_from_db();self.assertEqual(issue.status,'tracking')
        with patch('campus.security_service.collect',return_value=([{**CHECKS[0],'status':'unknown'}],{})):run_scan(self.root)
        issue.refresh_from_db();self.assertEqual(issue.status,'tracking')
        with patch('campus.security_service.collect',return_value=([{**CHECKS[0],'status':'pass'}],{})):run_scan(self.root)
        issue.refresh_from_db();self.assertEqual(issue.status,'resolved')
    def test_history_does_not_fabricate_missing_days(self):
        with patch('campus.security_service.collect',return_value=(CHECKS,{})):run_scan(self.root)
        r=self.client.get(reverse('security-daily'));history=r.context['history']
        self.assertEqual(len(history),14);self.assertEqual(sum(p['score'] is not None for p in history),1)
    def test_failed_login_never_records_password_or_raw_request(self):
        req=RequestFactory().post('/login/?secret=hidden',{'password':'PRIVATE_SECRET','medical':'PRIVATE_MEDICAL'})
        authenticate(req,username='missing-user',password='PRIVATE_SECRET')
        item=SecurityEvent.objects.filter(kind='login_failed').latest('pk')
        serialized=json.dumps({'kind':item.kind,'route':item.route,'method':item.method,'status':item.status_code})
        self.assertNotIn('PRIVATE_',serialized);self.assertNotIn('secret=',serialized)
    def test_configuration_evidence_never_exposes_secret(self):
        with override_settings(SECRET_KEY='NEVER_SHOW_THIS_SECRET_KEY_VALUE_123456789'):
            with patch('campus.security_service.local_port',return_value=False):checks,inventory=collect()
        self.assertNotIn('NEVER_SHOW',json.dumps([checks,inventory]))
    def test_local_probe_is_fixed_to_first_party_service(self):
        with patch('campus.security_service.local_port',return_value=False) as probe:collect()
        probe.assert_called_once_with(11434)

class BackupTests(TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.base=Path(self.folder.name);self.source=self.base/'source.sqlite3'
        with closing(sqlite3.connect(self.source)) as db:
            db.execute('CREATE TABLE fixture (value TEXT)');db.execute("INSERT INTO fixture VALUES ('test-only')");db.commit()
        self.override=override_settings(BASE_DIR=self.base);self.override.enable();self.addCleanup(self.override.disable)
    def test_real_sqlite_backup_then_tamper_detected(self):
        with patch('campus.security_service.database_path',return_value=self.source):row=create_backup(None)
        self.assertTrue(verify_backup(row));path=backup_path(row)
        with closing(sqlite3.connect(path)) as db:db.execute("INSERT INTO fixture VALUES ('changed')");db.commit()
        self.assertFalse(verify_backup(row));self.assertEqual(row.status,'failed')
    def test_backup_filename_cannot_escape_private_folder(self):
        row=SecurityBackup(filename='../outside.sqlite3')
        with self.assertRaises(ValueError):backup_path(row)
    def test_missing_backup_is_not_reported_verified(self):
        with patch('campus.security_service.database_path',return_value=self.source):row=create_backup(None)
        backup_path(row).unlink();self.assertFalse(verify_backup(row))
