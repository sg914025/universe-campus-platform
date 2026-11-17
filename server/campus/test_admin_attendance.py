from datetime import timedelta
from unittest.mock import patch
import uuid
from django.test import TestCase,Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone
from .models import Venue,VenueBooking,StaffAuditEvent
from .attendance import manual_release,release_due,bookable,check_in
from .booking_forms import slot_start
class AdminAttendanceTests(TestCase):
 def setUp(self):
  User=get_user_model();self.staff=User.objects.create_user('attendance_manager');self.staff.user_permissions.add(Permission.objects.get(content_type__app_label='campus',codename='manage_bookings'));self.user=User.objects.create_user('attendance_student');self.venue=Venue.objects.create(name='签到测试座位',kind='study',building='A');self.day=timezone.localdate()+timedelta(days=1);self.start=slot_start(self.day,'10');self.item=VenueBooking.objects.create(user=self.user,venue=self.venue,day=self.day,slot='10',request_key=uuid.uuid4(),checkin_deadline=self.start+timedelta(minutes=15));self.url=reverse('campus:booking-release',args=[self.item.pk]);self.client.force_login(self.staff)
 def test_role_post_and_csrf(self):
  self.assertEqual(self.client.get(self.url).status_code,405);self.client.force_login(self.user);self.assertEqual(self.client.post(self.url,{'reason':'维修'}).status_code,403)
  strict=Client(enforce_csrf_checks=True);strict.force_login(self.staff);self.assertEqual(strict.post(self.url,{'reason':'维修'}).status_code,403)
 def test_manual_record_and_idempotency(self):
  self.client.post(self.url,{'reason':'座椅维修'});self.item.refresh_from_db();self.assertEqual(self.item.status,'released');self.assertEqual(self.item.release_reason,'座椅维修');self.assertEqual(self.item.released_by,self.staff);self.assertIsNotNone(self.item.released_at)
  self.client.post(self.url,{'reason':'重复操作'});self.assertEqual(StaffAuditEvent.objects.filter(action='手动释放座位').count(),1)
  with patch('django.utils.timezone.now',return_value=self.start+timedelta(minutes=20)):self.assertTrue(bookable(self.venue,self.day,'10'))
 def test_reason_required_and_checked_confirmation(self):
  self.client.post(self.url,{'reason':' '});self.item.refresh_from_db();self.assertEqual(self.item.status,'reserved')
  self.item.checked_in_at=timezone.now();self.item.save();self.client.post(self.url,{'reason':'提前离开'});self.item.refresh_from_db();self.assertEqual(self.item.status,'reserved')
  self.client.post(self.url,{'reason':'提前离开','confirm_checked_in':'yes'});self.item.refresh_from_db();self.assertEqual(self.item.status,'released');self.assertIsNotNone(self.item.checked_in_at)
  self.assertEqual(check_in(self.user,self.item.pk)[1],'unavailable')
 def test_no_release_of_ended_bookings(self):
  with patch('django.utils.timezone.now',return_value=self.start+timedelta(hours=3)):self.assertFalse(manual_release(self.staff,self.item.pk,'已经结束'))
 def test_automatic_release_audit(self):
  with patch('django.utils.timezone.now',return_value=self.start+timedelta(minutes=16)):self.assertEqual(release_due(),1);self.assertEqual(release_due(),0)
  self.item.refresh_from_db();self.assertEqual(self.item.release_reason,'超时未签到');self.assertIsNotNone(self.item.released_at);self.assertIsNone(self.item.released_by);self.assertEqual(StaffAuditEvent.objects.filter(action='超时未签到自动释放').count(),1)
 def test_filters_and_safe_rendering(self):
  url=reverse('campus:booking-admin');response=self.client.get(url,{'state':'waiting','day':str(self.day)});self.assertContains(response,self.user.username);self.assertContains(response,'待签到')
  self.client.post(self.url,{'reason':'<script>alert(1)</script>'});response=self.client.get(url,{'state':'released','day':str(self.day)});self.assertContains(response,self.staff.username);self.assertContains(response,'&lt;script&gt;');self.assertNotContains(response,'<script>alert(1)</script>');self.assertEqual(self.client.get(url,{'state':'checked'}).context['page'].paginator.count,0)
