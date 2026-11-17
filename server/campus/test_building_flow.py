import json
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Venue
from .task_assistant import SESSION_KEY

class BuildingFlowTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('building-qa',password='qa-only')
        from accounts.models import Profile
        Profile.objects.create(user=self.user,full_name='楼栋测试',gender='other',age=20)
        self.client.force_login(self.user)
        self.a=Venue.objects.create(name='A-only-seat',kind='study',building='A')
        self.c=Venue.objects.create(name='C-only-seat',kind='study',building='C')

    def test_choose_building_before_seats(self):
        from django.urls import reverse
        url=reverse('campus:booking')
        response=self.client.get(url,{'kind':'study'})
        self.assertContains(response,'先选择自习楼栋')
        self.assertNotContains(response,'A-only-seat')
        response=self.client.get(url,{'kind':'study','building':'C'})
        self.assertContains(response,'C-only-seat')
        self.assertNotContains(response,'A-only-seat')
        self.assertNotContains(self.client.get(url,{'kind':'study','building':'invalid'}),'C-only-seat')

    def test_assistant_building_filter_and_cross_building_rejection(self):
        day=(timezone.localdate()+timedelta(days=1)).isoformat()
        session=self.client.session
        session[SESSION_KEY]={'user':self.user.pk,'key':'test-key','expires':timezone.now().timestamp()+600,'kind':'study','day':day,'slot':'14'}
        session.save()
        self.assertEqual(self.client.get('/api/assistant/state/').json()['phase'],'ask_building')
        response=self.client.post('/api/assistant/chat/',json.dumps({'selection':{'building':'C'}}),content_type='application/json')
        data=response.json()
        self.assertEqual(data['phase'],'choose_venue')
        self.assertEqual([v['id'] for v in data['venues']],[self.c.pk])
        forged={'draft_key':data['draft_key'],'venue_id':self.a.pk}
        self.assertEqual(self.client.post('/api/assistant/preview/',json.dumps(forged),content_type='application/json').status_code,400)
        self.assertEqual(self.client.post('/api/assistant/confirm/',json.dumps(forged),content_type='application/json').status_code,409)
        valid={'draft_key':data['draft_key'],'venue_id':self.c.pk}
        self.assertEqual(self.client.post('/api/assistant/confirm/',json.dumps(valid),content_type='application/json').json()['phase'],'done')

    def test_map_entry_in_sidebar(self):
        response=self.client.get('/')
        self.assertContains(response,'class="agenda-map-entry"')
