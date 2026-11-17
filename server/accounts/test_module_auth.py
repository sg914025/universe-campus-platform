# Author: UniVerse Team
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile


class ModuleAuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('20260077', password='Sturdy-Mint!73')
        Profile.objects.create(user=self.user, student_number='20260077', full_name='模块测试用户', gender='female', age=20)

    def test_each_entry_has_student_login_and_closed_registration(self):
        for module, name in [('forum', '校园广场'), ('errands', '校园跑腿'), ('guide', 'AI 导诊'), ('booking', '场地预约')]:
            with self.subTest(module=module):
                self.assertRedirects(self.client.get('/' + module + '/'), '/login/' + module + '/?next=/' + module + '/', fetch_redirect_response=False)
                login = self.client.get(reverse(module + '-login'))
                self.assertContains(login, name + '登录')
                self.assertContains(login, '学号')
                register = self.client.get(reverse(module + '-register'))
                self.assertContains(register, '校园账号说明')
                self.assertContains(register, '学校管理员统一导入')

    def test_module_login_destination_and_validation(self):
        for module in ('forum', 'errands', 'guide', 'booking'):
            self.client.logout()
            invalid = self.client.post(reverse(module + '-login'), {'username': self.user.username, 'password': 'wrong'})
            self.assertTrue(invalid.context['form'].errors)
            response = self.client.post(reverse(module + '-login'), {'username': self.user.username, 'password': 'Sturdy-Mint!73'})
            self.assertEqual(response['Location'], '/' + module + '/')

    def test_module_registration_post_cannot_create_user(self):
        response = self.client.post(reverse('booking-register'), {'username': '20260078', 'password1': 'Anything!73'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='20260078').exists())

    def test_module_auth_rejects_external_next(self):
        response = self.client.post(reverse('forum-login'), {'username': self.user.username, 'password': 'Sturdy-Mint!73', 'next': 'https://example.com/'})
        self.assertEqual(response['Location'], '/')
