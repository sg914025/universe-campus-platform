import json
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, Client, SimpleTestCase
from django.utils import timezone
from accounts.models import Profile
from .models import Venue, VenueBooking
from .task_assistant import SESSION_KEY
from .task_intent import rules, extract


class IntentTests(SimpleTestCase):
    def test_four_languages_and_explicit_times(self):
        today=timezone.localdate()
        for text in ('我想预约明天下午两点的自习室','Book a study room tomorrow at 2pm','Хочу завтра в 14:00 место для учёбы','明日の午後二時に自習室を予約したい'):
            with self.subTest(text=text):
                result=rules(text,today)
                self.assertEqual((result['kind'],result['day'],result['slot']),('study',(today+timedelta(days=1)).isoformat(),'14'))

    def test_ambiguous_period_has_no_default_slot(self):
        result=rules('Хочу завтра после обеда место для учёбы',timezone.localdate())
        self.assertNotIn('slot',result)

    def test_dates_ranges_and_unsupported_minutes(self):
        for text,slot in [('2026-10-20 14:00','14'),('14-16','14'),('2-4pm','14'),('15:00','invalid'),('14:30','invalid'),('14:30–16:30','invalid')]:
            with self.subTest(text=text):self.assertEqual(rules(text,timezone.localdate()).get('slot'),slot)

    def test_model_output_is_bounded_and_fails_closed(self):
        today=timezone.localdate()
        with patch('campus.task_intent.request_json',return_value={'response':json.dumps({'intent':'booking','kind':'study','day':'','slot':''})}):
            self.assertEqual(extract('a quiet nook please',today),({'intent':'booking','kind':'study'},'local_ai'))
        for response in ('{"intent":"execute"}','[]','{"intent":"booking","kind":"study","day":"","slot":"15"}'):
            with patch('campus.task_intent.request_json',return_value={'response':response}):self.assertEqual(extract('a quiet nook please',today),({},'rules'))


class TaskAssistantTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('task_student',password='Example-Only!2941')
        Profile.objects.create(user=self.user,full_name='办事测试同学',gender='other',age=20)
        self.other=User.objects.create_user('task_other')
        self.venue=Venue.objects.create(name='独立测试座位',kind='study')
        self.day=timezone.localdate()+timedelta(days=1)
        self.client.force_login(self.user)

    def post(self,path,data):return self.client.post('/api/assistant/'+path+'/',data=json.dumps(data),content_type='application/json')
    def draft(self):
        first=self.post('chat',{'message':'明天下午两点预约自习室'}).json()
        self.assertEqual(first['phase'],'ask_building')
        return self.post('chat',{'selection':{'building':'other'}}).json()
    def confirm(self,state,venue=None):
        return self.post('confirm',{'draft_key':state['draft_key'],'venue_id':venue or self.venue.pk})

    def test_chat_and_affirmation_never_create_booking(self):
        state=self.draft()
        self.assertEqual(state['phase'],'choose_venue')
        self.assertIn(self.venue.pk,[item['id'] for item in state['venues']])
        self.post('chat',{'message':'确认'})
        self.assertFalse(VenueBooking.objects.exists())
        self.assertNotIn('明天下午',json.dumps(dict(self.client.session),ensure_ascii=False))

    def test_ambiguity_is_clarified_instead_of_defaulted(self):
        result=self.post('chat',{'message':'Хочу завтра после обеда место для учёбы'}).json()
        self.assertEqual(result['phase'],'ask_building')
        result=self.post('chat',{'selection':{'building':'other'}}).json()
        self.assertEqual(result['phase'],'ask_slot')
        self.assertNotIn('slot',result['draft'])
        self.assertFalse(VenueBooking.objects.exists())

    def test_explicit_confirmation_and_retry_are_one_booking(self):
        state=self.draft()
        for _ in range(2):
            response=self.confirm(state)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['phase'],'done')
        record=VenueBooking.objects.get()
        self.assertEqual((record.user_id,record.venue_id,record.day,record.slot),(self.user.pk,self.venue.pk,self.day,'14'))
        self.assertContains(self.client.get('/my-services/'),self.venue.name)
        self.post('chat',{'reset':True})
        record.refresh_from_db();self.assertEqual(record.status,'reserved')

    def test_occupied_venue_or_user_conflict_is_rejected(self):
        state=self.draft()
        VenueBooking.objects.create(user=self.other,venue=self.venue,day=self.day,slot='14',request_key=uuid.uuid4())
        self.assertEqual(self.confirm(state).status_code,409)
        another=Venue.objects.create(name='其他测试座位',kind='study')
        VenueBooking.objects.create(user=self.user,venue=another,day=self.day,slot='14',request_key=uuid.uuid4())
        third=Venue.objects.create(name='第三测试座位',kind='study')
        self.assertEqual(self.confirm(state,third.pk).status_code,409)
        self.assertEqual(VenueBooking.objects.count(),2)

    def test_closed_and_wrong_kind_resources_are_rejected(self):
        state=self.draft()
        self.venue.active=False;self.venue.save()
        self.assertEqual(self.confirm(state).status_code,409)
        court=Venue.objects.create(name='测试篮球场',kind='basketball')
        self.assertEqual(self.confirm(state,court.pk).status_code,409)
        self.assertFalse(VenueBooking.objects.exists())

    def test_changed_expired_and_foreign_drafts_are_rejected(self):
        old=self.draft()
        self.post('chat',{'selection':{'slot':'16'}})
        self.assertEqual(self.confirm(old).status_code,409)
        current=self.client.get('/api/assistant/state/').json()
        session=self.client.session;draft=session[SESSION_KEY];draft['expires']=0;session[SESSION_KEY]=draft;session.save()
        self.assertEqual(self.confirm(current).status_code,409)
        state=self.draft()
        session=self.client.session;draft=session[SESSION_KEY];draft['user']=self.other.pk;session[SESSION_KEY]=draft;session.save()
        self.assertEqual(self.confirm(state).status_code,409)
        self.assertFalse(VenueBooking.objects.exists())

    def test_validation_auth_csrf_and_methods(self):
        self.assertEqual(self.client.get('/api/assistant/confirm/').status_code,405)
        for data in ({'message':'hello','user':self.other.pk},{'selection':{'kind':'study','day':str(self.day)}},{'selection':{'slot':'15'}},{'reset':False}):
            self.assertEqual(self.post('chat',data).status_code,400)
        self.assertEqual(self.client.post('/api/assistant/chat/',data='[',content_type='application/json').status_code,400)
        self.assertEqual(self.post('confirm',{'draft_key':'x','venue_id':True}).status_code,400)
        protected=Client(enforce_csrf_checks=True);protected.force_login(self.user)
        self.assertEqual(protected.post('/api/assistant/chat/',{'message':'study'}).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get('/assistant/').status_code,302)
        self.assertEqual(self.client.get('/api/assistant/state/').status_code,401)
        self.assertEqual(self.post('chat',{'message':'study'}).status_code,401)

    def test_invalid_date_and_time_prompt_without_booking(self):
        for text in ('自习室 2099-01-01 14:00','明天自习室 15:00','明天自习室 14:30'):
            self.post('chat',{'reset':True})
            response=self.post('chat',{'message':text}).json()
            self.assertNotEqual(response['phase'],'choose_venue')
        self.assertFalse(VenueBooking.objects.exists())

    def test_navigation_is_links_only_and_clears_draft(self):
        for text,intent in [('找同学','friends'),('快递帮忙','help'),('我想导诊','health'),('取消预约','manage')]:
            self.draft()
            result=self.post('chat',{'message':text}).json()
            self.assertEqual((result['phase'],result['intent']),('navigate',intent))
            self.assertTrue(all(item['url'].startswith('/') for item in result['actions']))
            self.assertNotIn(SESSION_KEY,self.client.session)
        self.assertFalse(VenueBooking.objects.exists())

    def test_language_change_preserves_draft_and_translates_response(self):
        self.draft()
        before=self.client.get('/api/assistant/state/').json()
        for language in ('en','ru','ja'):
            self.client.cookies['campus_language']=language
            after=self.client.get('/api/assistant/state/').json()
            self.assertEqual(after['draft'],before['draft'])
            self.assertNotEqual(after['message'],before['message'])
            self.assertEqual(self.client.get('/assistant/').status_code,200)
