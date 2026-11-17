from io import StringIO
from pathlib import Path
import tempfile
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.template.loader import get_template
from accounts.models import Profile
from triage.models import Department, DoctorProfile
from 帖子.models import post


class SuperAdministratorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = 'Reliable-Campus!384'
        cls.root = User.objects.create_superuser('top_admin_test', password=cls.password)
        cls.student = User.objects.create_user('student_new_test', password=cls.password)
        Profile.objects.create(user=cls.student, full_name='测试同学', gender='female')
        cls.department = Department.objects.filter(active=True).first()

    def payload(self, role, username):
        return {'username': username, 'full_name': '业务测试账号', 'role': role, 'department': self.department.pk, 'password1': self.password, 'password2': self.password,
                'is_staff': 'on', 'is_superuser': 'on'}

    def test_superadmin_login_and_creation_are_private(self):
        self.assertContains(self.client.get('/management/'), '/management/login/superadmin/')
        self.assertEqual(self.client.get('/management/accounts/').status_code, 302)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get('/management/accounts/').status_code, 403)
        self.assertEqual(self.client.post('/management/accounts/', self.payload('campus', 'forbidden_new')).status_code, 403)
        self.assertFalse(User.objects.filter(username='forbidden_new').exists())
        self.client.logout()
        response = self.client.post('/management/login/superadmin/', {'username': self.root.username, 'password': self.password})
        self.assertRedirects(response, '/management/overview/')

    def test_created_roles_have_only_requested_permissions(self):
        self.client.force_login(self.root)
        for role in ('doctor', 'campus', 'booking'):
            response = self.client.post('/management/accounts/', self.payload(role, 'created_' + role))
            self.assertRedirects(response, '/management/accounts/')
            user = User.objects.get(username='created_' + role)
            self.assertTrue(user.check_password(self.password))
            self.assertFalse(user.is_superuser)
            self.assertFalse(user.is_staff)
            self.assertEqual(user.has_perm('campus.manage_campus'), role == 'campus')
            self.assertEqual(user.has_perm('campus.manage_bookings'), role == 'booking')
            self.assertEqual(DoctorProfile.objects.filter(user=user, department=self.department).exists(), role == 'doctor')
        self.client.force_login(User.objects.get(username='created_campus'))
        self.assertEqual(self.client.get('/management/accounts/').status_code, 403)

    def test_invalid_doctor_duplicate_username_and_superadmin_role_rejected(self):
        self.client.force_login(self.root)
        payload = self.payload('doctor', 'missing_dept')
        payload['department'] = ''
        self.assertContains(self.client.post('/management/accounts/', payload), '创建医生账号必须选择科室。')
        self.assertFalse(User.objects.filter(username='missing_dept').exists())
        self.client.post('/management/accounts/', self.payload('campus', 'unique_admin'))
        self.assertContains(self.client.post('/management/accounts/', self.payload('booking', 'UNIQUE_ADMIN')), '该账号已存在，请更换账号。')
        self.client.post('/management/accounts/', self.payload('superadmin', 'injected_root'))
        self.assertFalse(User.objects.filter(username='injected_root').exists())

    def test_user_content_not_translated_and_action_preview_removed(self):
        post.objects.create(author=self.student, title='取消订单并退款', content='我的帖子内容不能被改写。')
        self.client.force_login(self.student)
        self.client.post('/language/', {'language': 'en'})
        response = self.client.get('/forum/')
        self.assertContains(response, '取消订单并退款')
        self.assertContains(response, 'Campus forum')
        self.assertNotContains(self.client.get('/'), 'id="mascot-motion"')

    def test_all_project_templates_compile(self):
        from django.conf import settings
        for path in Path(settings.BASE_DIR).rglob('*.html'):
            if 'templates' not in path.parts or '.venv' in path.parts:
                continue
            name = path.relative_to(Path(settings.BASE_DIR) / 'templates') if path.is_relative_to(Path(settings.BASE_DIR) / 'templates') else Path(*path.parts[path.parts.index('templates')+1:])
            get_template(str(name).replace('\\', '/'))

    def test_bootstrap_never_changes_existing_superadmin(self):
        original = self.root.password
        output = StringIO()
        with tempfile.TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)):
            call_command('ensure_campus_superadmin', stdout=output)
            self.assertFalse((Path(folder) / 'private_credentials').exists())
        self.root.refresh_from_db()
        self.assertEqual(self.root.password, original)
