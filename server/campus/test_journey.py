import uuid,json
from datetime import timedelta,date
from unittest.mock import patch
from django.test import TestCase,SimpleTestCase,Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.db import IntegrityError
from accounts.models import Profile
from .models import Venue,VenueBooking,VenueWaitlist
from . import waitlist
from .meaning import compare

class MeaningTests(SimpleTestCase):
    def test_four_language_dates_and_times_align(self):
        today=date(2026,10,18)
        examples=['明天下午两点预约羽毛球场','Book badminton tomorrow at 2pm','Завтра в 14:00 бадминтон','明日の14時にバドミントン']
        for text in examples:
            result=compare(text,'2026-10-19 14:00 badminton',today)
            self.assertEqual(result['status'],'aligned',(text,result))
    def test_missing_negation_and_changed_dates_are_blocked(self):
        for original,translated in [('周五下午除了15:00都可以','Friday 15:00'),('明天14:00羽毛球','后天14:00羽毛球'),('3 people 14:00','2 people 14:00')]:
            self.assertEqual(compare(original,translated,date(2026,10,18))['status'],'mismatch')
    def test_unknown_is_not_a_false_pass(self):
        self.assertEqual(compare('想找一个安静的地方','Нужно тихое место',date(2026,10,18))['status'],'review')
        self.assertEqual(compare('不要14:00','не в 14:00',date(2026,10,18))['status'],'review')
    def test_russian_numeric_date(self):
        self.assertEqual(compare('19.10.2026 14:00','2026-10-19 14:00',date(2026,10,18))['status'],'aligned')

class JourneyTests(TestCase):
    def setUp(self):
        self.users=[]
        for i in range(4):
            user=User.objects.create_user('journey_user_'+str(i))
            Profile.objects.create(user=user,full_name='测试用户',age=20,gender='other');self.users.append(user)
        self.owner,self.first,self.second,self.outsider=self.users
        self.venue=Venue.objects.create(name='校园测试场地',kind='badminton',location='教学楼1层')
        self.day=timezone.localdate()+timedelta(days=1);self.slot='14'
        self.client.force_login(self.first)
    def reserve(self,user,venue=None):
        return waitlist.reserve(user,venue or self.venue,self.day,self.slot,uuid.uuid4())
    def occupied_queue(self):
        booking=self.reserve(self.owner)
        first=waitlist.join(self.first,self.venue,self.day,self.slot)
        second=waitlist.join(self.second,self.venue,self.day,self.slot)
        return booking,first,second
    def data(self,**extra):return {'day':self.day.isoformat(),'slot':self.slot,'request_key':str(uuid.uuid4()),**extra}
    def test_fifo_hold_claim_and_retry(self):
        booking,first,second=self.occupied_queue()
        waitlist.cancel_booking(self.owner,booking.pk)
        first.refresh_from_db();second.refresh_from_db()
        self.assertEqual(first.status,'offered');self.assertEqual(second.status,'waiting')
        with self.assertRaises(IntegrityError):self.reserve(self.outsider)
        record=waitlist.claim(first,self.first)
        self.assertEqual(waitlist.claim(first,self.first).pk,record.pk)
        self.assertEqual(VenueBooking.objects.filter(venue=self.venue,status='reserved').count(),1)
    def test_expiry_promotes_next_and_old_user_cannot_claim(self):
        booking,first,second=self.occupied_queue();waitlist.cancel_booking(self.owner,booking.pk);first.refresh_from_db()
        with patch('campus.waitlist.timezone.now',return_value=first.offered_until+timedelta(seconds=1)):
            waitlist.refresh(first)
            with self.assertRaises(IntegrityError):waitlist.claim(first,self.first)
        first.refresh_from_db();second.refresh_from_db();self.assertEqual(first.status,'expired');self.assertEqual(second.status,'offered')
    def test_overlapping_booking_is_skipped(self):
        booking,first,second=self.occupied_queue()
        self.reserve(self.first,Venue.objects.create(name='另一场地',kind='study'))
        waitlist.cancel_booking(self.owner,booking.pk)
        first.refresh_from_db();second.refresh_from_db();self.assertEqual(first.status,'ineligible');self.assertEqual(second.status,'offered')
    def test_duplicate_queue_and_withdrawal_do_not_jump(self):
        booking,first,second=self.occupied_queue()
        self.assertEqual(waitlist.join(self.first,self.venue,self.day,self.slot).pk,first.pk)
        waitlist.cancel_booking(self.owner,booking.pk);waitlist.leave(first)
        second.refresh_from_db();self.assertEqual(second.status,'offered')
    def test_queue_hold_also_blocks_existing_booking_page(self):
        booking,first,second=self.occupied_queue();waitlist.cancel_booking(self.owner,booking.pk)
        self.client.force_login(self.outsider)
        response=self.client.post(reverse('campus:booking-venue',args=[self.venue.pk]),self.data())
        self.assertEqual(response.status_code,200)
        self.assertFalse(VenueBooking.objects.filter(user=self.outsider).exists())
    def test_preview_is_read_only_and_confirmation_is_idempotent(self):
        response=self.client.post(reverse('campus:booking-preview',args=[self.venue.pk]),self.data())
        self.assertTrue(response.context['token']);self.assertFalse(VenueBooking.objects.exists())
        token=response.context['token']
        self.client.post(reverse('campus:booking-commit'),{'token':token})
        self.client.post(reverse('campus:booking-commit'),{'token':token})
        self.assertEqual(VenueBooking.objects.filter(user=self.first).count(),1)
    def test_cross_language_mismatch_blocks_preview_confirmation(self):
        response=self.client.post(reverse('campus:booking-preview',args=[self.venue.pk]),self.data(original='明天14:00羽毛球',translated='后天14:00羽毛球'))
        self.assertEqual(response.context['result']['status'],'mismatch');self.assertFalse(response.context['token'])
        self.assertFalse(VenueBooking.objects.exists())
    def test_unknown_meaning_requires_explicit_review(self):
        response=self.client.post(reverse('campus:booking-preview',args=[self.venue.pk]),self.data(original='a quiet corner',translated='安静角落'))
        token=response.context['token'];self.assertTrue(response.context['needs_review'])
        self.client.post(reverse('campus:booking-commit'),{'token':token})
        self.assertFalse(VenueBooking.objects.exists())
        self.client.post(reverse('campus:booking-commit'),{'token':token,'review_confirmed':'yes'})
        self.assertTrue(VenueBooking.objects.exists())
    def test_preview_token_is_owner_bound_and_expires(self):
        response=self.client.post(reverse('campus:booking-preview',args=[self.venue.pk]),self.data());token=response.context['token']
        self.client.force_login(self.second);self.client.post(reverse('campus:booking-commit'),{'token':token})
        self.assertFalse(VenueBooking.objects.exists())
        self.client.force_login(self.first)
        with patch('django.core.signing.time.time',return_value=timezone.now().timestamp()+301):self.client.post(reverse('campus:booking-commit'),{'token':token})
        self.assertFalse(VenueBooking.objects.exists())
    def test_private_card_calendar_and_queue_actions(self):
        record=self.reserve(self.first)
        response=self.client.get(reverse('campus:service-card',args=[record.pk]))
        self.assertContains(response,'Русский');self.assertIn('no-store',response.headers['Cache-Control'])
        calendar=self.client.get(reverse('campus:service-calendar',args=[record.pk]));self.assertContains(calendar,'BEGIN:VCALENDAR')
        self.assertNotIn('journey_user_',calendar.content.decode())
        self.client.force_login(self.second)
        self.assertEqual(self.client.get(reverse('campus:service-card',args=[record.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('campus:service-calendar',args=[record.pk])).status_code,404)
        row=waitlist.join(self.second,self.venue,self.day,self.slot)
        self.client.force_login(self.first)
        self.assertEqual(self.client.post(reverse('campus:waitlist'),{'entry':row.pk,'action':'claim'}).status_code,404)
        self.assertEqual(self.client.get(reverse('campus:waitlist-admin')).status_code,403)
    def test_new_writes_require_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.first)
        for name,args in [('campus:booking-preview',[self.venue.pk]),('campus:booking-commit',[]),('campus:waitlist',[])]:
            self.assertEqual(client.post(reverse(name,args=args),{}).status_code,403)

    def test_assistant_preview_is_read_only_and_respects_offer_owner(self):
        booking,first,second=self.occupied_queue();waitlist.cancel_booking(self.owner,booking.pk)
        session=self.client.session
        from .task_assistant import SESSION_KEY
        key=str(uuid.uuid4())
        session[SESSION_KEY]={'user':self.first.pk,'key':key,'expires':timezone.now().timestamp()+600,'kind':self.venue.kind,'day':self.day.isoformat(),'slot':self.slot}
        session.save()
        before=VenueBooking.objects.count()
        response=self.client.post(reverse('campus:assistant-preview'),json.dumps({'draft_key':key,'venue_id':self.venue.pk}),content_type='application/json')
        self.assertTrue(response.json()['available'])
        self.assertEqual(VenueBooking.objects.count(),before)
