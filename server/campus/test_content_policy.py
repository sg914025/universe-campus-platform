from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase,SimpleTestCase
from django.urls import reverse
from .content_policy import contains_blocked,ERROR
from .ui_language import translate
from 帖子.forms import post_form,comment_form
from 跑腿.forms import task_form
from 帖子.models import post,profile,tag
from 跑腿.models import task,wallet_record

class WordRuleTests(SimpleTestCase):
    def test_normalization_and_multilingual_rules(self):
        for text in ['代考接单','代 考接单','代·考','代\u200b考','傻Ｂ','FUCK YOU','Ｆｕｃｋ　Ｙｏｕ','продам наркотики','пошел на хуй','麻薬売ります']:
            with self.subTest(text=text):self.assertTrue(contains_blocked(text))
    def test_normal_services_and_discussion_are_not_blanket_blocked(self):
        for text in ['取快递顺便买药','反诈骗知识分享','如何防范赌博骗局','图书馆扫码入座','帮忙打印资料','推荐电影和学习方法','A class assignment about fraud prevention','Let us study together','Мне нужна помощь с учёбой','一緒に勉強しよう']:
            with self.subTest(text=text):self.assertFalse(contains_blocked(text))
    def test_errors_translated_in_four_languages(self):
        for code in ['en','ru','ja']:self.assertNotEqual(translate(ERROR,code),ERROR)

class PublicationRuleTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('publication_qa')
        self.person,_=profile.objects.get_or_create(user=self.user)
        self.person.balance=Decimal('50');self.person.save()
        self.client.force_login(self.user)
        self.post_data={'title':'一起学习','category':'学习交流','content':'图书馆找学习搭子','tags_text':'校园'}
        self.task_data={'title':'代取快递','category':'express','description':'取件后送到宿舍','address':'一号楼大厅','phone':'13800138000','price':'2.00'}
    def test_post_title_content_and_tags_are_checked(self):
        for field in ['title','content','tags_text']:
            data={**self.post_data,field:'代\u200b考'};form=post_form(data)
            self.assertFalse(form.is_valid());self.assertIn(field,form.errors)
    def test_rejected_post_does_not_create_post_or_tags(self):
        response=self.client.post(reverse('campus:post_create'),{**self.post_data,'title':'代 考接单'})
        self.assertContains(response,ERROR);self.assertFalse(post.objects.exists());self.assertFalse(tag.objects.exists())
    def test_edit_cannot_bypass_rules(self):
        item=post.objects.create(author=self.user,title='学习日常',content='正常内容',category='校园生活')
        response=self.client.post(reverse('campus:post_edit',args=[item.pk]),{**self.post_data,'content':'刷单返利'})
        self.assertContains(response,ERROR);item.refresh_from_db();self.assertEqual(item.content,'正常内容')
    def test_rejected_errand_never_charges_balance(self):
        for field in ['title','description','address']:
            response=self.client.post(reverse('campus:errand_create'),{**self.task_data,field:'出售银行卡'})
            self.assertContains(response,ERROR)
        self.person.refresh_from_db();self.assertEqual(self.person.balance,50)
        self.assertFalse(task.objects.exists());self.assertFalse(wallet_record.objects.exists())
    def test_valid_errand_still_publishes_and_prepays(self):
        response=self.client.post(reverse('campus:errand_create'),self.task_data)
        self.assertEqual(response.status_code,302);self.assertEqual(task.objects.count(),1)
        self.person.refresh_from_db();self.assertEqual(self.person.balance,48)
    def test_valid_post_still_publishes(self):
        self.assertEqual(self.client.post(reverse('campus:post_create'),self.post_data).status_code,302)
        self.assertEqual(post.objects.count(),1)
    def test_comment_form_uses_the_same_rules(self):
        form=comment_form({'content':'fuck you'});self.assertFalse(form.is_valid());self.assertIn('content',form.errors)
    def test_valid_forms_accept_normal_text(self):
        self.assertTrue(post_form(self.post_data).is_valid());self.assertTrue(task_form(self.task_data).is_valid())
    def test_error_is_rendered_in_selected_language(self):
        for code in ['en','ru','ja']:
            session=self.client.session;session['campus_language']=code;session.save()
            response=self.client.post(reverse('campus:errand_create'),{**self.task_data,'description':'刷单返利'})
            self.assertContains(response,translate(ERROR,code))
