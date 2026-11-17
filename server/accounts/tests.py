# Author: UniVerse Team
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import Profile


class AccountFlowTests(TestCase):
    password = 'Sturdy-Mint!73'

    def make_student(self, username='20260088', **profile_changes):
        user = User.objects.create_user(username=username, password=self.password)
        values = {'student_number': username, 'full_name': '测试用户', 'gender': 'female', 'age': 18}
        values.update(profile_changes)
        Profile.objects.create(user=user, **values)
        return user

    def test_home_is_portal_and_guide_requires_login(self):
        self.assertContains(self.client.get(reverse('home')), '校园跑腿')
        self.assertRedirects(self.client.get(reverse('guide')), '/login/guide/?next=/guide/', fetch_redirect_response=False)

    def test_registration_endpoint_never_creates_account(self):
        response = self.client.post(reverse('register'), {'username': '20260099', 'password1': self.password})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '学校管理员统一导入')
        self.assertFalse(User.objects.filter(username='20260099').exists())

    def test_existing_student_login_logout_and_wrong_password(self):
        self.make_student()
        response = self.client.post(reverse('login'), {'username': '20260088', 'password': 'wrong'})
        self.assertContains(response, '学号或密码不正确')
        self.assertNotIn(SESSION_KEY, self.client.session)
        response = self.client.post(reverse('login'), {'username': '20260088', 'password': self.password})
        self.assertRedirects(response, reverse('home'))
        self.assertIn(SESSION_KEY, self.client.session)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'))

    def test_login_ignores_external_redirect(self):
        self.make_student()
        response = self.client.post(reverse('login'), {'username': '20260088', 'password': self.password, 'next': '//example.com/'})
        self.assertRedirects(response, reverse('home'))

    def test_incomplete_existing_user_must_finish_profile(self):
        user = User.objects.create_user(username='existing_user', password=self.password)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse('home')), reverse('profile'))
        self.client.post(reverse('profile'), {'full_name': '已有用户', 'gender': 'other', 'age': ''})
        self.assertTrue(user.guide_profile.is_complete)

    def test_profile_update_is_scoped_to_logged_in_user(self):
        user = self.make_student()
        other = self.make_student('20260089', full_name='另一用户', gender='male')
        self.client.force_login(user)
        self.client.post(reverse('profile'), {'full_name': '更新姓名', 'gender': 'male', 'age': '32', 'user': other.pk})
        self.assertEqual(Profile.objects.get(user=user).full_name, '更新姓名')
        self.assertEqual(Profile.objects.get(user=other).full_name, '另一用户')

    def test_name_is_escaped(self):
        user = self.make_student(full_name='<script>alert(1)</script>')
        self.client.force_login(user)
        response = self.client.get(reverse('guide'))
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_csrf_enforced_on_login_profile_logout_and_password_change(self):
        user = self.make_student()
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse('login'), {'username': user.username, 'password': self.password}).status_code, 403)
        client.force_login(user)
        self.assertEqual(client.post(reverse('profile'), {'full_name': '测试用户', 'gender': 'male'}).status_code, 403)
        self.assertEqual(client.post(reverse('password-change'), {}).status_code, 403)
        self.assertEqual(client.post(reverse('logout')).status_code, 403)

    def test_authenticated_pages_are_not_cached(self):
        user = self.make_student()
        self.client.force_login(user)
        self.assertIn('no-store', self.client.get(reverse('home'))['Cache-Control'])
        self.assertIn('no-store', self.client.get(reverse('profile'))['Cache-Control'])
