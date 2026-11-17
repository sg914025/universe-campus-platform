import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,Client,SimpleTestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from .models import CampusServicePlan,Venue,VenueBooking
from .service_plans import candidate

class PlanDetectionTests(SimpleTestCase):
    def test_four_languages_and_single_service_unchanged(self):
        for text in ('我刚来学校，想认识同学，周末打羽毛球','I want to meet students and play badminton this weekend','Хочу познакомиться со студентами и играть в бадминтон на выходных','友達を作って週末にバドミントンをしたい'):
            self.assertEqual(candidate(text)['steps'],['friends','time','booking'])
        self.assertIsNone(candidate('解释一下递归'))
        self.assertIsNone(candidate('明天预约羽毛球'))
        self.assertIsNone(candidate('取消羽毛球预约，认识同学'))

class ServicePlanTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('plan_qa')
        self.other=User.objects.create_user('plan_other')
        self.client.force_login(self.user)
        self.url=reverse('campus:service-plans')
        self.chat=reverse('task-assistant-chat')
        day=timezone.localdate()+timedelta(days=1)
        while day.weekday()!=5:day+=timedelta(days=1)
        self.day=day
        self.venue=Venue.objects.create(name='计划验证羽毛球场',kind='badminton',location='校园体育馆')
    def make(self):
        response=self.client.post(self.chat,json.dumps({'message':'我刚来学校，想认识同学，周末打羽毛球'}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['phase'],'plan')
        return response.json()['plan']
    def act(self,plan,action,**extra):
        return self.client.post(self.url,json.dumps({'id':plan['id'],'revision':plan['revision'],'action':action,**extra}),content_type='application/json')
    def publish(self, plan):
        from .service_plans import friend_post_url
        item=CampusServicePlan.objects.get(pk=plan['id'])
        response=self.client.post(friend_post_url(item),{'title':'周末找羽毛球伙伴','category':'交友','content':'刚到学校，想约同学周末一起打球。','tags_text':''})
        self.assertEqual(response.status_code,302)
        return self.client.get(self.url).json()['plan']
    def prepare_booking(self):
        plan=self.make()
        plan=self.act(plan,'accept').json()['plan']
        plan=self.publish(plan)
        plan=self.act(plan,'time',day=self.day.isoformat(),slot='14').json()['plan']
        return plan
    def test_no_automatic_actions_and_resume(self):
        plan=self.make()
        self.assertEqual(plan['progress'],0)
        self.assertFalse(plan['accepted'])
        self.assertEqual(VenueBooking.objects.count(),0)
        self.assertEqual(self.act(plan,'complete').status_code,400)
        self.assertEqual(self.client.get(self.url).json()['plan']['id'],plan['id'])
        self.make();self.assertEqual(CampusServicePlan.objects.count(),1)
    def test_order_revision_and_weekend(self):
        first=self.make()
        accepted=self.act(first,'accept').json()['plan']
        self.assertEqual(self.act(first,'complete').status_code,409)
        self.assertEqual(self.act(accepted,'time',day=self.day.isoformat(),slot='14').status_code,400)
        self.assertEqual(self.act(accepted,'complete').status_code,400)
        plan=self.publish(accepted)
        monday=self.day+timedelta(days=2)
        self.assertEqual(self.act(plan,'time',day=monday.isoformat(),slot='14').status_code,400)
        self.assertEqual(self.act(plan,'complete').status_code,400)
    def test_real_booking_completes_exact_plan(self):
        plan=self.prepare_booking()
        response=self.act(plan,'book');self.assertEqual(response.status_code,200)
        plan=response.json()['plan'];draft=response.json()['assistant']
        self.assertEqual(VenueBooking.objects.count(),0)
        self.assertEqual(plan['progress'],2)
        data={'draft_key':draft['draft_key'],'venue_id':self.venue.pk}
        response=self.client.post(reverse('task-assistant-confirm'),json.dumps(data),content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['plan']['state'],'active')
        self.assertEqual(response.json()['plan']['current'],'share')
        self.assertEqual(response.json()['plan']['progress'],3)
        self.assertEqual(VenueBooking.objects.count(),1)
        self.assertEqual(self.client.post(reverse('task-assistant-confirm'),json.dumps(data),content_type='application/json').status_code,200)
        self.assertEqual(VenueBooking.objects.count(),1)
    def test_cancel_plan_invalidates_inflight_booking(self):
        plan=self.prepare_booking();data=self.act(plan,'book').json();plan=data['plan'];draft=data['assistant']
        self.assertEqual(self.act(plan,'cancel').status_code,200)
        response=self.client.post(reverse('task-assistant-confirm'),json.dumps({'draft_key':draft['draft_key'],'venue_id':self.venue.pk}),content_type='application/json')
        self.assertEqual(response.status_code,409)
        self.assertEqual(VenueBooking.objects.count(),0)
    def test_retime_requires_reconfirmation(self):
        plan=self.prepare_booking();plan=self.act(plan,'retime').json()['plan']
        self.assertEqual(plan['current'],'time')
        self.assertEqual(plan['day'],'')
        self.assertEqual(self.act(plan,'book').status_code,400)
    def test_owner_csrf_and_login(self):
        plan=self.make();self.client.force_login(self.other)
        self.assertIsNone(self.client.get(self.url).json()['plan'])
        self.assertEqual(self.act(plan,'accept').status_code,404)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.user)
        self.assertEqual(strict.post(self.url,json.dumps({'id':plan['id'],'revision':plan['revision'],'action':'accept'}),content_type='application/json').status_code,403)
        self.client.logout();self.assertEqual(self.client.get(self.url).status_code,302)
    def test_single_service_keeps_existing_flow(self):
        response=self.client.post(self.chat,json.dumps({'message':'明天预约羽毛球场','channel':'task'}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertNotEqual(response.json()['phase'],'plan')
        self.assertEqual(CampusServicePlan.objects.count(),0)
