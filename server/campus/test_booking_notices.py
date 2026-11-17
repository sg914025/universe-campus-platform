import uuid
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from .models import Venue,VenueBooking,VenueWaitlist,BookingNotice
from .booking_forms import slot_start
from .booking_notices import remind_checkins,process_attendance
from .attendance import release_due
from . import waitlist
class BookingNoticeTests(TestCase):
 def setUp(self):
  User=get_user_model();self.owner=User.objects.create_user('notice-owner');self.first=User.objects.create_user('notice-first');self.second=User.objects.create_user('notice-second');self.venue=Venue.objects.create(kind='study',building='A',name='通知测试座位');self.day=timezone.localdate()+timedelta(days=1);self.start=slot_start(self.day,'10');self.booking=waitlist.reserve(self.owner,self.venue,self.day,'10',uuid.uuid4())
 def test_reminder_once_and_read_does_not_recreate(self):
  with patch('django.utils.timezone.now',return_value=self.start-timedelta(minutes=11)):self.assertEqual(remind_checkins(),0)
  with patch('django.utils.timezone.now',return_value=self.start-timedelta(minutes=10)):
   self.assertEqual(remind_checkins(),1);notice=BookingNotice.objects.get(kind='checkin_reminder');self.assertEqual(notice.user,self.owner);notice.is_read=True;notice.save();self.assertEqual(remind_checkins(),0);self.assertEqual(BookingNotice.objects.count(),1)
 def test_checked_in_and_cancelled_not_reminded(self):
  self.booking.checked_in_at=timezone.now();self.booking.save()
  with patch('django.utils.timezone.now',return_value=self.start):self.assertEqual(remind_checkins(),0)
  self.booking.checked_in_at=None;self.booking.status='cancelled';self.booking.save()
  with patch('django.utils.timezone.now',return_value=self.start):self.assertEqual(remind_checkins(),0)
 def test_after_start_queue_survives_then_release_notifies_first_only(self):
  one=waitlist.join(self.first,self.venue,self.day,'10');two=waitlist.join(self.second,self.venue,self.day,'10')
  with patch('django.utils.timezone.now',return_value=self.start+timedelta(minutes=1)):
   waitlist.refresh(one);one.refresh_from_db();self.assertEqual(one.status,'waiting')
  with patch('django.utils.timezone.now',return_value=self.start+timedelta(minutes=16)):
   process_attendance();process_attendance();self.assertEqual(BookingNotice.objects.filter(kind='seat_released',user=self.owner).count(),1);self.assertEqual(BookingNotice.objects.filter(kind='waitlist_offer',user=self.first).count(),1);self.assertFalse(BookingNotice.objects.filter(kind='waitlist_offer',user=self.second).exists());one.refresh_from_db();self.assertEqual(one.status,'offered');self.assertEqual(one.offered_until,self.start+timedelta(minutes=31))
   claimed=waitlist.claim(one,self.first);self.assertEqual(claimed.user,self.first);self.assertEqual(claimed.checkin_deadline,self.start+timedelta(minutes=31))
 def test_expired_offer_automatically_advances(self):
  one=waitlist.join(self.first,self.venue,self.day,'10');two=waitlist.join(self.second,self.venue,self.day,'10')
  with patch('django.utils.timezone.now',return_value=self.start+timedelta(minutes=16)):process_attendance()
  with patch('django.utils.timezone.now',return_value=self.start+timedelta(minutes=32)):
   process_attendance();one.refresh_from_db();two.refresh_from_db();self.assertEqual(one.status,'expired');self.assertEqual(two.status,'offered');self.assertTrue(BookingNotice.objects.filter(user=self.second,kind='waitlist_offer').exists());self.assertFalse(VenueBooking.objects.filter(user=self.second,status='reserved').exists())
 def test_notice_owner_read_and_endpoint_integration(self):
  with patch('django.utils.timezone.now',return_value=self.start-timedelta(minutes=10)):remind_checkins()
  notice=BookingNotice.objects.get();self.client.force_login(self.first);self.assertEqual(self.client.post(reverse('service-notice-read'),{'kind':'booking','id':notice.pk}).status_code,404)
  self.client.force_login(self.owner);response=self.client.get(reverse('my-services'));self.assertContains(response,'赴约签到提醒');self.assertContains(response,reverse('campus:booking-checkin',args=[self.booking.pk]));self.assertEqual(self.client.get(reverse('service-unread')).json()['unread'],1);self.client.post(reverse('service-notice-read'),{'kind':'booking','id':notice.pk});notice.refresh_from_db();self.assertTrue(notice.is_read)
 def test_offer_notice_rolls_back_with_transaction(self):
  one=waitlist.join(self.first,self.venue,self.day,'10')
  with self.assertRaises(RuntimeError):
   with transaction.atomic():
    waitlist.cancel_booking(self.owner,self.booking.pk);raise RuntimeError('rollback')
  self.assertFalse(BookingNotice.objects.exists());one.refresh_from_db();self.assertEqual(one.status,'waiting')
