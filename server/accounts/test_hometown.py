from django.test import TestCase,override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Profile

@override_settings(ENABLE_HERITAGE=True)
class HometownTests(TestCase):
    def student(self,**changes):
        user=User.objects.create_user('hometown_test',password='Sturdy-Mint!73')
        values={'student_number':'hometown_test','full_name':'家乡测试同学','gender':'female','age':20,**changes}
        Profile.objects.create(user=user,**values)
        self.client.force_login(user)
        return user

    def test_registration_saves_optional_location_and_recommends_only_matching_source(self):
        profile=self.student(hometown_province='海南省',hometown_city='海口').guide_profile
        self.assertEqual((profile.hometown_province,profile.hometown_city),('海南省','海口'))
        response=self.client.get('/')
        self.assertEqual(response.context['initial_outfit']['id'],'li')
        self.assertNotContains(response,'海口')
        self.assertContains(response,'非遗元素创意展示')
        self.assertEqual(self.client.get('/heritage/').status_code,404)

    def test_location_is_optional_and_unsupported_region_is_not_mislabelled(self):
        self.student()
        self.assertEqual(User.objects.get(username='hometown_test').guide_profile.hometown_province,'')
        response=self.client.get('/',{'province':'辽宁省'})
        self.assertIsNone(response.context['recommended'])
        self.assertContains(response,'暂未收录辽宁省')
        response=self.client.get('/',{'province':'invalid'})
        self.assertEqual(response.context['province'],'')

    def test_profile_update_and_invalid_province(self):
        self.student()
        invalid=self.client.post(reverse('profile'),{'full_name':'家乡测试同学','gender':'female','age':'20','hometown_province':'unknown','hometown_city':''})
        self.assertEqual(invalid.status_code,200)
        response=self.client.post(reverse('profile'),{'full_name':'家乡测试同学','gender':'female','age':'20','hometown_province':'贵州省','hometown_city':'贵阳'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(User.objects.get(username='hometown_test').guide_profile.hometown_province,'贵州省')
        self.assertEqual(self.client.get('/').context['initial_outfit']['id'],'miao')

@override_settings(ENABLE_HERITAGE=False)
class DisabledHeritageTests(TestCase):
    def test_disabled_feature_is_hidden_and_existing_location_is_preserved(self):
        from .forms import RegistrationForm,ProfileFields
        self.assertNotIn('hometown_province',RegistrationForm().fields)
        self.assertNotIn('hometown_city',ProfileFields().fields)
        self.assertNotContains(self.client.get('/'),'heritage-home')
        self.assertNotContains(self.client.get('/register/'),'生源地')
        user=User.objects.create_user('paused_heritage',password='Sturdy-Mint!73')
        Profile.objects.create(user=user,full_name='暂停测试用户',gender='female',age=20,hometown_province='海南省',hometown_city='海口')
        self.client.force_login(user)
        self.client.post('/profile/',{'full_name':'暂停测试用户','gender':'female','age':'20','hometown_province':'贵州省','hometown_city':'贵阳'})
        user.guide_profile.refresh_from_db()
        self.assertEqual(user.guide_profile.hometown_city,'海口')
