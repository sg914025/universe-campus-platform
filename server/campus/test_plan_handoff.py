import json
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from .models import CampusServicePlan
from 帖子.models import post
from .service_plans import friend_post_url

class PlanHandoffTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('handoff_qa')
        self.client.force_login(self.user)
        self.plan=CampusServicePlan.objects.create(user=self.user,source='认识同学周末羽毛球',kind='badminton',steps=['friends','time','booking'],accepted=True)
        self.url=reverse('campus:service-plans')
    def act(self,action):
        self.plan.refresh_from_db()
        return self.client.post(self.url,json.dumps({'id':self.plan.pk,'revision':str(self.plan.revision),'action':action}),content_type='application/json')
    def test_cancelled_is_explicit_and_resumable(self):
        self.plan.state='cancelled';self.plan.completed=['friends'];self.plan.save()
        data=self.client.get(self.url).json()['plan']
        self.assertIn('已结束',data['instruction'])
        response=self.act('resume');self.assertEqual(response.status_code,200)
        data=response.json()['plan'];self.assertEqual(data['state'],'active');self.assertEqual(data['current'],'time');self.assertTrue(data['days'])
    def test_accept_redirects_to_post_form_and_initial_category(self):
        self.plan.accepted=False;self.plan.save()
        response=self.act('accept');self.assertIn('/forum/posts/new/?service_plan=',response.json()['next_url'])
        page=self.client.get(response.json()['next_url'])
        self.assertEqual(page.status_code,200)
        self.assertEqual(page.context['form']['category'].value(),'交友')
        self.assertEqual(post.objects.count(),0)
    def test_publish_returns_and_advances_only_on_success(self):
        url=friend_post_url(self.plan)
        response=self.client.post(url,{'title':'校园新生找羽毛球伙伴','category':'交友','content':'周末一起打球，欢迎同学参加。','tags_text':''})
        self.assertRedirects(response,reverse('task-assistant')+'#service-plan-panel',fetch_redirect_response=False)
        self.plan.refresh_from_db();self.assertEqual(self.plan.completed,['friends'])
        self.assertEqual(post.objects.count(),1)
    def test_invalid_post_and_wrong_category_do_not_advance(self):
        url=friend_post_url(self.plan)
        response=self.client.post(url,{'title':'','category':'交友','content':''})
        self.assertEqual(response.status_code,200)
        self.plan.refresh_from_db();self.assertEqual(self.plan.completed,[])
        self.client.post(url,{'title':'校园日常分享','category':'日常','content':'今天在学校散步','tags_text':''})
        self.plan.refresh_from_db();self.assertEqual(self.plan.completed,[])
    def test_other_user_cannot_use_link_and_active_conflict(self):
        other=User.objects.create_user('other_handoff')
        url=friend_post_url(self.plan);self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code,404)
        self.client.force_login(self.user);self.plan.state='cancelled';self.plan.save()
        CampusServicePlan.objects.create(user=self.user,source='another',steps=['help','health'])
        self.assertEqual(self.act('resume').status_code,409)

    def test_old_booking_draft_does_not_replace_current_plan(self):
        from .task_assistant import SESSION_KEY
        from django.utils import timezone
        previous=CampusServicePlan.objects.create(user=self.user,source='old',steps=['friends'],completed=['friends'],state='completed',accepted=True)
        session=self.client.session
        session[SESSION_KEY]={'user':self.user.pk,'plan_id':previous.pk,'confirmed':99999,'expires':timezone.now().timestamp()+600,'key':'old'}
        session.save()
        response=self.client.get(reverse('task-assistant-state'))
        self.assertEqual(response.json()['plan']['id'],self.plan.pk)
        self.assertNotIn('receipt',response.json())
