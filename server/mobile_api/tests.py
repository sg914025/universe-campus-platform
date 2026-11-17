"""Shared client integration tests. Author: UniVerse Team. All data is fictional."""
import json, uuid
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core import signing
from django.utils import timezone
from django.urls import reverse
from accounts.models import Profile
from 帖子.models import profile, follow, post, chat_message
from campus.models import Venue, VenueBooking, VenueWaitlist, CampusServicePlan, FriendMoment
from campus.booking_forms import slot_start
from campus import waitlist


class MobileIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password='Test-Campus!6492'
        cls.user=User.objects.create_user('mobile_student',password=cls.password)
        cls.other=User.objects.create_user('mobile_friend',password=cls.password)
        cls.stranger=User.objects.create_user('mobile_stranger',password=cls.password)
        for u in (cls.user,cls.other,cls.stranger):
            Profile.objects.create(user=u,full_name='虚构测试学生',gender='other')
            profile.objects.create(user=u,nickname=u.username)
        cls.venue=Venue.objects.create(name='A 楼 01 号座位',kind='study',building='A',floor=1,active=True,is_demo=True,location='测试自习室')
        cls.day=timezone.localdate()+timedelta(days=2)

    def setUp(self):
        cache.clear()
        self.client=Client(enforce_csrf_checks=True)
        self.token=self.sign_in(self.user)

    def sign_in(self,user):
        response=self.client.post('/api/mobile/v1/auth/login/',json.dumps({'username':user.username,'password':self.password}),content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        return response.json()['token']

    def call(self,route,data=None,token=None,method=None):
        kwargs={'HTTP_AUTHORIZATION':'Bearer '+(token or self.token)}
        if data is None and method!='post':return self.client.get('/api/mobile/v1/'+route+'/',**kwargs)
        return self.client.post('/api/mobile/v1/'+route+'/',json.dumps(data or {}),content_type='application/json',**kwargs)

    def reserve(self,user=None,slot='14',venue=None,key=None):
        return waitlist.reserve(user or self.user,venue or self.venue,self.day,slot,key or uuid.uuid4())

    def test_auth_me_and_cookie_alone_cannot_access_api(self):
        self.assertEqual(self.call('me').json()['user']['id'],self.user.pk)
        self.assertEqual(self.client.get('/api/mobile/v1/overview/').status_code,401)
        self.assertEqual(self.client.get('/api/mobile/v1/me/',HTTP_AUTHORIZATION='Bearer bogus').status_code,401)

    def test_logout_revokes_native_token(self):
        self.assertEqual(self.call('auth/logout',{}).status_code,200)
        self.assertEqual(self.call('me').status_code,401)

    def test_first_login_gate_and_password_rotation(self):
        Profile.objects.filter(user=self.user).update(must_change_password=True)
        self.assertEqual(self.call('bookings').status_code,403)
        response=self.call('auth/password',{'old_password':self.password,'new_password1':'New-Mobile!5328','new_password2':'New-Mobile!5328'})
        self.assertEqual(response.status_code,200,response.content)
        new=response.json()['token'];self.assertNotEqual(new,self.token)
        self.assertEqual(self.call('me').status_code,401)
        self.assertEqual(self.call('bookings',token=new).status_code,200)
        self.assertFalse(Profile.objects.get(user=self.user).must_change_password)

    def test_public_metadata_has_no_private_fields(self):
        response=self.client.get('/api/mobile/v1/bootstrap/')
        self.assertEqual(response.status_code,200,response.content)
        self.assertIn('buildings',response.json())
        self.assertNotIn('bookings',response.json())
        self.assertIsNone(response.json()['user'])

    def test_booking_idempotency_and_conflict(self):
        data={'venue_id':self.venue.pk,'day':str(self.day),'slot':'14','request_key':str(uuid.uuid4())}
        first=self.call('bookings',data)
        self.assertEqual(first.status_code,201,first.content)
        self.assertEqual(self.call('bookings',data).json()['booking']['id'],first.json()['booking']['id'])
        self.assertEqual(VenueBooking.objects.filter(user=self.user).count(),1)
        other_token=self.sign_in(self.other)
        data['request_key']=str(uuid.uuid4())
        self.assertEqual(self.call('bookings',data,token=other_token).status_code,409)

    def test_foreign_booking_hidden_and_cancel_releases(self):
        row=self.reserve()
        other_token=self.sign_in(self.other)
        self.assertEqual(self.call(f'bookings/{row.pk}/cancel',{},token=other_token).status_code,404)
        self.assertEqual(self.call(f'bookings/{row.pk}/cancel',{}).status_code,200)
        row.refresh_from_db();self.assertEqual(row.status,'cancelled')

    def test_venue_state_matches_bookings_and_waitlist_holds(self):
        self.reserve(self.other)
        query=f'/api/mobile/v1/venues/?day={self.day}&slot=14&kind=study&building=A'
        response=self.client.get(query,HTTP_AUTHORIZATION='Bearer '+self.token)
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['venues'][0]['state'],'occupied')
        VenueBooking.objects.update(status='cancelled')
        VenueWaitlist.objects.create(venue=self.venue,user=self.other,day=self.day,slot='14',status='offered',offered_until=timezone.now()+timedelta(minutes=10))
        response=self.client.get(query,HTTP_AUTHORIZATION='Bearer '+self.token)
        self.assertEqual(response.json()['venues'][0]['state'],'held')

    def test_session_backed_assistant_draft_survives_native_requests(self):
        response=self.call('assistant/chat',{'selection':{'kind':'study'}})
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['phase'],'ask_building')
        self.call('assistant/chat',{'selection':{'building':'A'}})
        self.call('assistant/chat',{'selection':{'day':str(self.day)}})
        response=self.call('assistant/chat',{'selection':{'slot':'14'}})
        self.assertEqual(response.status_code,200,response.content)
        state=self.call('assistant/state').json()
        self.assertEqual(state['phase'],'choose_venue')
        response=self.call('assistant/confirm',{'draft_key':state['draft_key'],'venue_id':self.venue.pk})
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(VenueBooking.objects.filter(user=self.user).count(),1)

    def test_plan_friend_post_completes_real_step(self):
        response=self.call('assistant/chat',{'message':'我刚来学校，想认识同学，周末打羽毛球','channel':'auto','external_allowed':False,'history':[]})
        self.assertEqual(response.status_code,200,response.content)
        plan=response.json()['plan']
        response=self.call('plans',{'id':plan['id'],'revision':plan['revision'],'action':'accept'})
        self.assertEqual(response.status_code,200,response.content)
        plan=response.json()['plan']
        data={'title':'周末一起打羽毛球','content':'虚构测试内容，希望认识一起运动的同学。','category':'交友','service_plan':plan['id'],'revision':plan['revision']}
        response=self.call('posts',data)
        self.assertEqual(response.status_code,201,response.content)
        plan=CampusServicePlan.objects.get(pk=plan['id'])
        self.assertIn('friends',plan.completed)
        self.assertEqual(plan.linked_post_id,response.json()['post']['id'])

    def test_hidden_posts_excluded(self):
        post.objects.create(author=self.other,title='HIDDEN',content='hidden',is_hidden=True)
        self.assertNotContains(self.call('posts'),'HIDDEN')

    def test_chat_requires_mutual_follow_and_third_party_cannot_read(self):
        self.assertEqual(self.call(f'friends/{self.other.pk}/messages').status_code,403)
        self.call(f'friends/{self.other.pk}/follow',{})
        self.assertEqual(self.call(f'friends/{self.other.pk}/messages').status_code,403)
        follow.objects.create(user=self.other,target=self.user)
        self.assertEqual(self.call(f'friends/{self.other.pk}/messages',{'content':'Hello from the campus'}).status_code,201)
        self.assertContains(self.call(f'friends/{self.other.pk}/messages'),'Hello from the campus')
        stranger_token=self.sign_in(self.stranger)
        self.assertEqual(self.call(f'friends/{self.other.pk}/messages',token=stranger_token).status_code,403)

    def test_moments_are_only_self_and_friends(self):
        FriendMoment.objects.create(author=self.stranger,content='PRIVATE-STRANGER-MOMENT')
        self.assertNotContains(self.call('moments'),'PRIVATE-STRANGER-MOMENT')
        response=self.call('moments',{'content':'A fictional moment'})
        self.assertEqual(response.status_code,201,response.content)
        self.assertContains(self.call('moments'),'A fictional moment')

    def test_booking_share_ownership_and_mutual_friend(self):
        row=self.reserve()
        self.assertEqual(self.call(f'bookings/{row.pk}/share',{'friend_id':self.other.pk}).status_code,404)
        follow.objects.create(user=self.user,target=self.other);follow.objects.create(user=self.other,target=self.user)
        response=self.call(f'bookings/{row.pk}/share',{'friend_id':self.other.pk})
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(self.call(f'friends/{self.other.pk}/messages').json()['messages'][0]['booking']['id'],row.pk)

    def test_bridge_is_short_lived_single_use_and_scoped(self):
        for path in ('https://bad.example','//bad.example','/admin/','/campus-map/\\bad','/campus-map/\r\nLocation: nope'):
            self.assertEqual(self.call('web-ticket',{'path':path}).status_code,400)
        response=self.call('web-ticket',{'path':'/campus-map/?area=A'})
        self.assertEqual(response.status_code,200,response.content)
        target=response.json()['url'];web=Client()
        self.assertEqual(web.get(target).status_code,302)
        self.assertEqual(int(web.session['_auth_user_id']),self.user.pk)
        self.assertEqual(web.get(target).status_code,404)

    def test_bridge_rejects_changed_password_or_expired_ticket(self):
        target=self.call('web-ticket',{'path':'/campus-map/'}).json()['url']
        self.user.set_password('Changed-Password!732');self.user.save()
        self.assertEqual(Client().get(target).status_code,404)
        self.assertEqual(Client().get('/mobile/bridge/'+'a'*64+'/').status_code,404)

    def test_checkin_rejects_foreign_code_and_accepts_valid_window(self):
        row=self.reserve();token=signing.dumps({'booking':row.pk,'user':self.user.pk},salt='universe-seat-checkin')
        wrong=signing.dumps({'booking':row.pk,'user':self.other.pk},salt='universe-seat-checkin')
        self.assertEqual(self.call(f'bookings/{row.pk}/checkin',{'token':wrong}).status_code,403)
        self.assertEqual(self.call(f'bookings/{row.pk}/checkin',{'token':token}).status_code,409)
        with patch('campus.attendance.timezone.now',return_value=slot_start(self.day,'14')):
            response=self.call(f'bookings/{row.pk}/checkin',{'token':token})
        self.assertEqual(response.status_code,200,response.content)
        row.refresh_from_db();self.assertIsNotNone(row.checked_in_at)

    def test_health_and_errand_payload_shape(self):
        self.assertEqual(self.call('health/parts').status_code,200)
        self.assertEqual(self.call('errands').status_code,200)
        self.assertEqual(self.call('overview').status_code,200)

    def test_non_json_and_wrong_methods_rejected(self):
        self.assertEqual(self.client.post('/api/mobile/v1/auth/login/',{'username':'test'}).status_code,400)
        self.assertEqual(self.client.delete('/api/mobile/v1/me/').status_code,405)
        self.assertEqual(self.call('web-ticket').status_code,400)

    def test_inactive_account_cannot_use_existing_token(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.call('overview').status_code,401)
