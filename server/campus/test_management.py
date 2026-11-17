from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase
from triage.models import Department, DoctorProfile


class ManagementAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = 'Strong-Campus!824'
        cls.student = User.objects.create_user('student_staff_test', password=cls.password)
        cls.campus = User.objects.create_user('campus_staff_test', password=cls.password)
        cls.booking = User.objects.create_user('booking_staff_test', password=cls.password)
        cls.doctor = User.objects.create_user('doctor_staff_test', password=cls.password)
        cls.campus.user_permissions.add(Permission.objects.get(content_type__app_label='campus', codename='manage_campus'))
        cls.booking.user_permissions.add(Permission.objects.get(content_type__app_label='campus', codename='manage_bookings'))
        department = Department.objects.filter(active=True).first() or Department.objects.create(slug='test', name='测试科室')
        DoctorProfile.objects.create(user=cls.doctor, department=department, display_name='测试医生')

    def test_portal_and_correct_login_destinations(self):
        self.assertContains(self.client.get('/'), '/management/')
        self.assertContains(self.client.get('/management/'), '/management/login/doctor/')
        for role, user, target in [('doctor', self.doctor, '/doctor/'), ('campus', self.campus, '/campus-admin/'), ('booking', self.booking, '/campus-admin/bookings/')]:
            self.client.logout()
            response = self.client.post('/management/login/' + role + '/', {'username': user.username, 'password': self.password})
            self.assertRedirects(response, target, fetch_redirect_response=False)
            self.assertEqual(self.client.get(target).status_code, 200)
            self.assertEqual(self.client.get('/').status_code, 200)  # staff do not need patient profiles

    def test_roles_cannot_cross_backends_or_authenticate_as_wrong_role(self):
        for role in ('doctor', 'campus', 'booking'):
            response = self.client.post('/management/login/' + role + '/', {'username': self.student.username, 'password': self.password})
            self.assertContains(response, '该账号没有所选后台的权限')
            self.assertNotIn('_auth_user_id', self.client.session)
        for user, blocked in [(self.campus, ['/doctor/', '/campus-admin/bookings/']), (self.booking, ['/doctor/', '/campus-admin/', '/campus-admin/errands/']), (self.doctor, ['/campus-admin/', '/campus-admin/bookings/'])]:
            self.client.force_login(user)
            for path in blocked:
                self.assertEqual(self.client.get(path).status_code, 403, path)
            self.client.logout()

    def test_old_entry_points_use_matching_management_login(self):
        for path, role in [('/doctor/', 'doctor'), ('/campus-admin/', 'campus'), ('/campus-admin/bookings/', 'booking')]:
            response = self.client.get(path)
            self.assertEqual(urlsplit(response['Location']).path, '/management/login/' + role + '/')
            self.assertEqual(parse_qs(urlsplit(response['Location']).query)['next'], [path])
        self.assertRedirects(self.client.get('/doctor/login/'), '/management/login/doctor/', fetch_redirect_response=False)
        response = self.client.get('/login/?next=/campus-admin/bookings/')
        self.assertEqual(urlsplit(response['Location']).path, '/management/login/booking/')
        response = self.client.post('/doctor/login/', {'username': self.doctor.username, 'password': self.password})
        self.assertRedirects(response, '/doctor/', fetch_redirect_response=False)

    def test_next_is_scoped_and_cannot_redirect_external_or_other_role(self):
        for value in ['https://example.com/', '//example.com/', '/doctor/', '/management/login/campus/', '/campus-admin/bookings/']:
            response = self.client.post('/management/login/campus/', {'username': self.campus.username, 'password': self.password, 'next': value})
            self.assertEqual(response['Location'], '/campus-admin/')
            self.client.logout()
        response = self.client.post('/management/login/booking/', {'username': self.booking.username, 'password': self.password, 'next': '/campus-admin/bookings/?day=2026-10-16'})
        self.assertEqual(response['Location'], '/campus-admin/bookings/?day=2026-10-16')

    def test_language_persists_and_translates_home_portal_and_error(self):
        for code, home_text, title, error in [('en', 'Your campus life,', 'Choose your workspace', 'This account cannot access this workspace.'), ('ru', 'Твоя жизнь в кампусе', 'Выберите рабочий раздел', 'У этой учётной записи нет доступа')]:
            response = self.client.post('/language/', {'language': code, 'next': '/management/'})
            self.assertEqual(response['Location'], '/management/')
            self.assertContains(self.client.get('/'), home_text)
            self.assertContains(self.client.get('/management/'), title)
            response = self.client.post('/management/login/booking/', {'username': self.student.username, 'password': self.password})
            self.assertContains(response, error)
        self.assertEqual(self.client.post('/language/', {'language': 'bad'}).status_code, 400)
        self.assertEqual(self.client.post('/language/', {'language': 'zh', 'next': 'https://example.com/'})['Location'], '/')

    def test_csrf_and_logout(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/management/login/campus/', {'username': self.campus.username, 'password': self.password}).status_code, 403)
        self.assertEqual(client.post('/language/', {'language': 'en'}).status_code, 403)
        self.client.force_login(self.booking)
        self.assertEqual(self.client.get('/management/logout/').status_code, 405)
        self.assertRedirects(self.client.post('/management/logout/'), '/management/')
