import uuid
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone
from .models import Venue,VenueBooking,VenueWaitlist,BookingNotice
from . import waitlist
class NoticeAdminTests(TestCase):
 def setUp(self):
  User=get_user_model();self.staff=User.objects.create_user('notice-record-manager');self.staff.user_permissions.add(Permission.objects.get(content_type__app_label='campus',codename='manage_bookings'));self.user=User.objects.create_user('notice-record-recipient');self.other=User.objects.create_user('other-recipient');self.venue=Venue.objects.create(kind='study',building='A',name='通知记录座位');self.day=timezone.localdate()+timedelta(days=1)
  self.booking=VenueBooking.objects.create(user=self.user,venue=self.venue,day=self.day,slot='10',request_key=uuid.uuid4());self.reminder=BookingNotice.objects.create(user=self.user,kind='checkin_reminder',event_key='test-reminder',booking=self.booking)
  self.queue=VenueWaitlist.objects.create(user=self.other,venue=self.venue,day=self.day,slot='14',status='offered',offered_until=timezone.now()+timedelta(minutes=15));self.offer=BookingNotice.objects.create(user=self.other,kind='waitlist_offer',event_key=f'offered:{self.queue.pk}',waitlist=self.queue);self.url=reverse('campus:booking-notice-admin');self.client.force_login(self.staff)
 def test_permission_and_readonly(self):
  self.assertEqual(self.client.get(self.url).status_code,200);self.assertEqual(self.client.post(self.url).status_code,405);self.client.force_login(self.user);self.assertEqual(self.client.get(self.url).status_code,403);self.client.logout();self.assertEqual(self.client.get(self.url).status_code,302)
 def test_filters_and_view_does_not_mark_read(self):
  response=self.client.get(self.url,{'kind':'checkin_reminder','q':self.user.username,'read':'no','day':timezone.localdate().isoformat()});self.assertEqual(response.context['page'].paginator.count,1);self.assertContains(response,self.user.username);self.reminder.refresh_from_db();self.assertFalse(self.reminder.is_read);self.assertIsNone(self.reminder.read_at);self.assertIn('no-store',response['Cache-Control'])
  self.assertEqual(self.client.get(self.url,{'confirmation':'pending'}).context['counts']['total'],1)
  with patch('django.utils.timezone.now',return_value=self.queue.offered_until+timedelta(seconds=1)):self.assertEqual(self.client.get(self.url,{'confirmation':'expired'}).context['counts']['total'],1)
 def test_read_time_recorded_and_visible(self):
  self.client.force_login(self.user);now=timezone.now()
  with patch('django.utils.timezone.now',return_value=now):self.client.post(reverse('service-notice-read'),{'kind':'booking','id':self.reminder.pk})
  self.reminder.refresh_from_db();self.assertTrue(self.reminder.is_read);self.assertEqual(self.reminder.read_at,now);self.client.force_login(self.staff);response=self.client.get(self.url,{'read':'yes'});self.assertEqual(response.context['counts']['read'],1);self.assertContains(response,'已读')
 def test_confirmation_time_and_later_cancellation(self):
  now=timezone.now()
  with patch('django.utils.timezone.now',return_value=now):record=waitlist.claim(self.queue,self.other)
  self.queue.refresh_from_db();self.assertEqual(self.queue.claimed_at,now);self.assertEqual(self.queue.booking,record);self.assertEqual(waitlist.claim(self.queue,self.other).pk,record.pk)
  record.status='cancelled';record.save();response=self.client.get(self.url,{'confirmation':'confirmed'});self.assertEqual(response.context['counts']['confirmed'],1);self.assertContains(response,'已确认预约');self.assertContains(response,'已取消');self.offer.refresh_from_db();self.assertFalse(self.offer.is_read)
 def test_legacy_read_has_no_fabricated_timestamp(self):
  self.reminder.is_read=True;self.reminder.save();response=self.client.get(self.url,{'read':'yes'});self.assertEqual(response.status_code,200);self.reminder.refresh_from_db();self.assertIsNone(self.reminder.read_at)
 def test_pagination_keeps_filter(self):
  BookingNotice.objects.bulk_create([BookingNotice(user=self.user,kind='checkin_reminder',event_key='page-'+str(i),booking=self.booking) for i in range(22)])
  response=self.client.get(self.url,{'kind':'checkin_reminder','read':'no','q':'notice-record','page':'1'});self.assertEqual(len(response.context['page']),20);self.assertContains(response,'kind=checkin_reminder');self.assertContains(response,'read=no')
