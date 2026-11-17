import uuid
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import Venue,VenueBooking
from .booking_forms import slot_start,BookingForm
from .attendance import release_due,check_in,bookable
from .checkin_views import token_for,map_url
from .waitlist import reserve
class SeatAttendanceTests(TestCase):
 def setUp(self):
  self.user=get_user_model().objects.create_user('arrival-owner');self.other=get_user_model().objects.create_user('arrival-other');self.venue=Venue.objects.create(name='A座位',kind='study',building='A',floor=2);self.day=timezone.localdate()+timedelta(days=1);self.start=slot_start(self.day,'10')
 def booking(self,**kw):
  return VenueBooking.objects.create(user=self.user,venue=self.venue,day=self.day,slot='10',request_key=uuid.uuid4(),**kw)
 def test_deadline_new_only(self):
  item=reserve(self.user,self.venue,self.day,'10',uuid.uuid4());self.assertEqual(item.checkin_deadline,self.start+timedelta(minutes=15))
 def test_checkin_window_and_idempotency(self):
  item=self.booking(checkin_deadline=self.start+timedelta(minutes=15))
  with patch('django.utils.timezone.now',return_value=self.start-timedelta(minutes=16)):self.assertEqual(check_in(self.user,item.pk)[1],'early')
  with patch('django.utils.timezone.now',return_value=self.start):
   self.assertEqual(check_in(self.user,item.pk)[1],'ok');self.assertEqual(check_in(self.user,item.pk)[1],'already')
  self.assertEqual(release_due(self.start+timedelta(minutes=16)),0)
 def test_release_and_late_rebooking(self):
  item=self.booking(checkin_deadline=self.start+timedelta(minutes=15))
  with patch('django.utils.timezone.now',return_value=self.start+timedelta(minutes=16)):
   self.assertEqual(release_due(),1);self.assertEqual(release_due(),0);item.refresh_from_db();self.assertEqual(item.status,'no_show');self.assertTrue(bookable(self.venue,self.day,'10'))
   again=reserve(self.other,self.venue,self.day,'10',uuid.uuid4());self.assertEqual(again.checkin_deadline,self.start+timedelta(minutes=31));self.assertEqual(VenueBooking.objects.filter(status='reserved').count(),1)
 def test_exact_deadline_denied(self):
  item=self.booking(checkin_deadline=self.start+timedelta(minutes=15))
  with patch('django.utils.timezone.now',return_value=self.start+timedelta(minutes=15)):self.assertEqual(check_in(self.user,item.pk)[1],'expired')
 def test_legacy_booking_preserved(self):
  item=self.booking();self.assertEqual(release_due(self.start+timedelta(hours=3)),0);item.refresh_from_db();self.assertEqual(item.status,'reserved')
 def test_owner_qr_and_signed_post(self):
  item=self.booking(checkin_deadline=self.start+timedelta(minutes=15));self.client.force_login(self.other)
  for name in ['booking-checkin','booking-qr','booking-navigate']:self.assertEqual(self.client.get(reverse('campus:'+name,args=[item.pk])).status_code,404)
  self.client.force_login(self.user);image=self.client.get(reverse('campus:booking-qr',args=[item.pk]));self.assertEqual(image.status_code,200);self.assertTrue(image.content.startswith(b'\x89PNG'));self.assertIn('no-store',image['Cache-Control'])
  with patch('django.utils.timezone.now',return_value=self.start):
   url=reverse('campus:booking-checkin',args=[item.pk]);self.assertEqual(self.client.get(url).status_code,200);item.refresh_from_db();self.assertIsNone(item.checked_in_at);self.assertEqual(self.client.post(url,{'token':'fake'}).status_code,400);self.assertEqual(self.client.post(url,{'token':token_for(item)}).status_code,302)
  self.assertIn('floor=2',map_url(item));self.assertIn('navigate=1',map_url(item))
