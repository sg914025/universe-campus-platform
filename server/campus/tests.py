import sqlite3
import tempfile
from pathlib import Path
from decimal import Decimal
from django.contrib.auth.models import User,Group,Permission
from django.core.management import call_command
from django.test import TestCase,Client
from django.urls import reverse
from accounts.models import Profile
from triage.models import DoctorProfile,Department
from 帖子.models import post,profile,comment
from 跑腿.models import task

class CampusIntegrationTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('campus_test',password='Sturdy-Mint!73')
        Profile.objects.create(user=self.user,full_name='校园测试用户',gender='female',age=28)
        self.other=User.objects.create_user('other_campus',password='Sturdy-Mint!73')
        profile.objects.create(user=self.other,nickname='论坛测试用户')
        self.post=post.objects.create(author=self.other,title='校园测试帖子',content='测试内容')
        self.task=task.objects.create(owner=self.other,title='功能测试取快递',description='测试订单',address='测试私密地址XYZ',phone='TEST-PHONE-XYZ',price=Decimal('5'))

    def test_portal_and_existing_app_routes(self):
        home=self.client.get(reverse('home'))
        for link in ('/forum/','/errands/','/guide/'):
            self.assertContains(home,link)
        self.client.force_login(self.user)
        for route in ('campus:home','campus:daily','campus:help','campus:friends','campus:errands'):
            response=self.client.get(reverse(route))
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'/guide/')

    def test_login_keeps_destination_and_same_session_reaches_all_modules(self):
        url=reverse('campus:post_create')
        self.assertRedirects(self.client.get(url),'/login/forum/?next='+url,fetch_redirect_response=False)
        self.client.post(reverse('login'),{'username':self.user.username,'password':'Sturdy-Mint!73','next':url})
        for route in ('guide','campus:profile','campus:errand_mine','campus:post_create'):
            response=self.client.get(reverse(route))
            self.assertEqual(response.status_code,200)
            self.assertIn('no-store',response['Cache-Control'])

    def test_post_comment_and_author_edit_keep_namespaced_urls(self):
        self.client.force_login(self.user)
        response=self.client.post(reverse('campus:post_create'),{'title':'我的校园测试','content':'新建测试内容','category':'校园生活'})
        created=post.objects.get(author=self.user)
        self.assertRedirects(response,reverse('campus:post_detail',args=[created.pk]))
        self.assertTrue(profile.objects.filter(user=self.user).exists())
        self.client.post(reverse('campus:post_detail',args=[self.post.pk]),{'content':'一条测试评论'})
        self.assertTrue(comment.objects.filter(post=self.post,author=self.user).exists())
        self.assertEqual(self.client.get(reverse('campus:post_edit',args=[self.post.pk])).status_code,404)

    def test_only_medical_accounts_are_not_public_forum_members(self):
        self.client.force_login(self.other)
        response=self.client.get(reverse('campus:user_search'),{'q':'campus_test'})
        self.assertContains(response,'没有找到相关用户')
        self.assertNotContains(response,reverse('campus:member',args=[self.user.pk]))
        self.assertEqual(self.client.get(reverse('campus:member',args=[self.user.pk])).status_code,404)

    def test_doctor_and_campus_manager_permissions_do_not_overlap(self):
        doctor=DoctorProfile.objects.create(user=self.user,department=Department.objects.get(slug='bone'),display_name='测试医生')
        self.client.force_login(doctor.user)
        self.assertEqual(self.client.get(reverse('campus:dashboard')).status_code,403)
        group=Group.objects.create(name='campus_moderators')
        group.permissions.add(Permission.objects.get(content_type__app_label='campus',codename='manage_campus'))
        self.other.groups.add(group);self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('campus:dashboard')).status_code,200)
        self.assertEqual(self.client.get(reverse('doctor-dashboard')).status_code,403)
        self.assertFalse(User.objects.get(pk=self.other.pk).is_staff)

    def test_errand_private_fields_and_proof_are_still_scoped(self):
        url=reverse('campus:errand_detail',args=[self.task.pk])
        self.assertRedirects(self.client.get(url),'/login/errands/?next='+url,fetch_redirect_response=False)
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(url),'TEST-PHONE-XYZ')
        self.assertNotContains(self.client.get(url),'测试私密地址XYZ')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('campus:errand_proof',args=[self.task.pk])).status_code,403)
        self.client.post(reverse('campus:errand_take',args=[self.task.pk]))
        self.task.refresh_from_db();self.assertEqual(self.task.runner_id,self.user.pk)
        self.assertContains(self.client.get(url),'TEST-PHONE-XYZ')

    def test_campus_post_still_requires_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(reverse('campus:post_create'),{'title':'test','content':'test','category':'校园生活'}).status_code,403)

class CampusImportTests(TestCase):
    def test_collision_is_preserved_and_import_is_idempotent(self):
        medical=User.objects.create_user('same_user',password='Different-Mint!73')
        password=medical.password
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'source.sqlite3';report=Path(folder)/'report.txt'
            source=sqlite3.connect(database)
            source.executescript('''CREATE TABLE auth_user(id INTEGER PRIMARY KEY,password TEXT,last_login TEXT,is_superuser INTEGER,username TEXT,first_name TEXT,last_name TEXT,email TEXT,is_staff INTEGER,is_active INTEGER,date_joined TEXT);
            CREATE TABLE "帖子_profile"(id INTEGER PRIMARY KEY,balance TEXT,avatar TEXT,user_id INTEGER REFERENCES auth_user(id),nickname TEXT,college TEXT,major TEXT,introduction TEXT);''')
            source.execute('INSERT INTO auth_user VALUES(?,?,?,?,?,?,?,?,?,?,?)',(1,password,None,1,'same_user','','','',1,1,'2026-10-03 01:02:03'))
            source.execute('INSERT INTO "帖子_profile" VALUES(?,?,?,?,?,?,?,?)',(1,'0','','1','测试昵称','','',''))
            source.commit();source.close()
            call_command('import_campus_project',database=str(database),report=str(report),verbosity=0)
            imported=User.objects.get(username='same_user_campus')
            self.assertFalse(imported.is_staff);self.assertFalse(imported.is_superuser)
            self.assertTrue(imported.is_campus_manager)
            self.assertEqual(imported.date_joined.hour,1)
            self.assertEqual(profile.objects.get(pk=1).user_id,imported.pk)
            self.assertEqual(User.objects.get(pk=medical.pk).password,password)
            call_command('import_campus_project',database=str(database),report=str(report),verbosity=0)
            self.assertEqual(User.objects.count(),2)


class CampusEntryAccessTests(TestCase):
    def test_guest_cannot_bypass_login_with_direct_url(self):
        from urllib.parse import parse_qs,urlsplit
        for path in ('/forum/','/forum/daily/','/errands/','/errands/1/','/booking/','/booking/venues/1/?day=2026-10-14','/forum','/errands','/booking'):
            response=self.client.get(path)
            self.assertEqual(response.status_code,302)
            location=urlsplit(response['Location'])
            self.assertEqual(location.path,'/login/'+path.strip('/').split('/')[0]+'/')
            self.assertEqual(parse_qs(location.query)['next'],[path])
            self.assertIn('no-store',response['Cache-Control'])
        self.assertEqual(self.client.get('/').status_code,200)

    def test_login_returns_to_selected_module_with_filters(self):
        user=User.objects.create_user('entry_access_test',password='Sturdy-Mint!73')
        Profile.objects.create(user=user,full_name='入口测试用户',gender='female',age=20)
        for destination in ('/forum/','/errands/?category=pickup','/booking/?kind=study'):
            self.client.logout()
            response=self.client.post('/login/',{'username':user.username,'password':'Sturdy-Mint!73','next':destination})
            self.assertEqual(response['Location'],destination)
            self.assertEqual(self.client.get(destination).status_code,200)
        self.client.logout()
        response=self.client.post('/login/',{'username':user.username,'password':'Sturdy-Mint!73','next':'https://example.com/'})
        self.assertEqual(response['Location'],'/')
