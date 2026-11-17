# Author: UniVerse Team
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from campus.models import StaffAuditEvent
from .models import Profile, StudentImportBatch


class StudentAccountImportTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser('student_import_root', password='Root-Account!73')

    def upload(self, content):
        return SimpleUploadedFile('students.csv', content.encode('utf-8-sig'), content_type='text/csv')

    def test_public_registration_is_closed(self):
        response = self.client.get(reverse('register'))
        self.assertContains(response, '不对校外人员开放注册')
        response = self.client.post(reverse('register'), {'username': '20260009', 'password1': 'Anything!73'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='20260009').exists())

    def test_superadmin_previews_then_imports_students_and_skips_existing_numbers(self):
        User.objects.create_user('20260002', password='Keep-Existing!73')
        self.client.force_login(self.root)
        csv_content = '学号,姓名,性别,年龄\n20260001,张三,男,18\n20260002,李四,女,19\n'
        response = self.client.post(reverse('management-accounts'), {
            'action': 'preview_students', 'csv_file': self.upload(csv_content),
        })
        batch = StudentImportBatch.objects.get()
        self.assertRedirects(response, reverse('management-accounts') + f'?preview={batch.pk}')
        self.assertFalse(User.objects.filter(username='20260001').exists())
        response = self.client.post(reverse('student-import-confirm', args=[batch.pk]))
        self.assertRedirects(response, reverse('student-activation-cards') + f'?batch={batch.pk}')
        student = User.objects.get(username='20260001')
        self.assertTrue(student.check_password('20260001'))
        self.assertEqual(student.guide_profile.student_number, '20260001')
        self.assertEqual(student.guide_profile.full_name, '张三')
        self.assertTrue(student.guide_profile.must_change_password)
        self.assertEqual(student.guide_profile.import_batch, batch)
        batch.refresh_from_db()
        self.assertEqual(batch.status, StudentImportBatch.Status.IMPORTED)
        self.assertTrue(StaffAuditEvent.objects.filter(action='确认导入学生账号').exists())
        self.assertTrue(User.objects.get(username='20260002').check_password('Keep-Existing!73'))

    def test_import_batch_can_be_rolled_back_without_deleting_accounts(self):
        self.client.force_login(self.root)
        response = self.client.post(reverse('management-accounts'), {
            'action': 'preview_students', 'csv_file': self.upload('学号,姓名\n20260011,周一\n'),
        })
        batch = StudentImportBatch.objects.get()
        self.client.post(reverse('student-import-confirm', args=[batch.pk]))
        student = User.objects.get(username='20260011')
        response = self.client.post(reverse('student-import-rollback', args=[batch.pk]))
        self.assertRedirects(response, reverse('management-accounts'))
        student.refresh_from_db(); batch.refresh_from_db()
        self.assertFalse(student.is_active)
        self.assertEqual(student.guide_profile.full_name, '周一')
        self.assertEqual(batch.status, StudentImportBatch.Status.ROLLED_BACK)

    def test_superadmin_can_manage_student_account(self):
        student = User.objects.create_user('20260012', password='Changed!731')
        Profile.objects.create(user=student, student_number='20260012', full_name='吴二', gender='other')
        self.client.force_login(self.root)
        self.client.post(reverse('student-account-action', args=[student.pk]), {'student_action': 'deactivate'})
        student.refresh_from_db(); self.assertFalse(student.is_active)
        self.client.post(reverse('student-account-action', args=[student.pk]), {'student_action': 'activate'})
        self.client.post(reverse('student-account-action', args=[student.pk]), {'student_action': 'reset_password'})
        student.refresh_from_db(); student.guide_profile.refresh_from_db()
        self.assertTrue(student.is_active)
        self.assertTrue(student.check_password('20260012'))
        self.assertTrue(student.guide_profile.must_change_password)

    def test_activation_card_qr_is_private_and_one_time(self):
        from .activation import token_for
        student = User.objects.create_user('20260006', password='20260006')
        Profile.objects.create(user=student, student_number='20260006', full_name='孙八', gender='other', must_change_password=True)
        self.client.force_login(self.root)
        session = self.client.session
        session['student_activation_ids'] = [student.pk]
        session.save()
        cards = self.client.get(reverse('student-activation-cards'))
        self.assertContains(cards, '孙八')
        self.assertContains(cards, '••••0006')
        image = self.client.get(reverse('student-activation-qr', args=[student.pk]))
        self.assertTrue(image.content.startswith(b'\x89PNG'))
        self.assertIn('no-store', image['Cache-Control'])
        token = token_for(student)
        self.client.logout()
        activate_url = reverse('student-activate', args=[token])
        self.assertEqual(self.client.get(activate_url).status_code, 200)
        wrong = self.client.post(activate_url, {'student_number': '20260006', 'full_name': '错误姓名',
            'new_password1': 'New-Student!736', 'new_password2': 'New-Student!736'})
        self.assertContains(wrong, '姓名与学校导入的信息不匹配')
        response = self.client.post(activate_url, {'student_number': '20260006', 'full_name': '孙八',
            'new_password1': 'New-Student!736', 'new_password2': 'New-Student!736'})
        self.assertRedirects(response, reverse('home'))
        student.refresh_from_db()
        self.assertTrue(student.check_password('New-Student!736'))
        self.assertEqual(self.client.get(activate_url).status_code, 400)

    def test_invalid_csv_creates_nothing_and_non_admin_cannot_import(self):
        bad = '学号,姓名\n20260003,王五\nbad-id,错误学生\n'
        self.client.force_login(self.root)
        response = self.client.post(reverse('management-accounts'), {
            'action': 'preview_students', 'csv_file': self.upload(bad),
        })
        self.assertContains(response, '学号须为 6–20 位数字')
        self.assertFalse(User.objects.filter(username='20260003').exists())
        self.client.force_login(User.objects.create_user('ordinary', password='Ordinary!73'))
        response = self.client.post(reverse('management-accounts'), {
            'action': 'preview_students', 'csv_file': self.upload('学号,姓名\n20260004,赵六\n'),
        })
        self.assertEqual(response.status_code, 403)

    def test_first_login_requires_password_change(self):
        student = User.objects.create_user('20260005', password='20260005')
        Profile.objects.create(user=student, student_number='20260005', full_name='钱七', gender='other', must_change_password=True)
        response = self.client.post(reverse('login'), {'username': '20260005', 'password': '20260005'})
        self.assertRedirects(response, reverse('password-change'))
        self.assertRedirects(self.client.get(reverse('home')), reverse('password-change'))
        response = self.client.post(reverse('password-change'), {
            'student_number': '20260005', 'full_name': '钱七', 'old_password': '20260005',
            'new_password1': 'New-Campus!735', 'new_password2': 'New-Campus!735',
        })
        self.assertRedirects(response, reverse('home'))
        student.refresh_from_db()
        student.guide_profile.refresh_from_db()
        self.assertTrue(student.check_password('New-Campus!735'))
        self.assertFalse(student.guide_profile.must_change_password)

    def test_csv_template_is_private(self):
        self.assertEqual(self.client.get(reverse('student-csv-template')).status_code, 302)
        self.client.force_login(self.root)
        response = self.client.get(reverse('student-csv-template'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('学号,姓名', response.content.decode('utf-8-sig'))
