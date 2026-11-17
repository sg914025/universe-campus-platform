import uuid
from datetime import timedelta
from io import StringIO
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Venue,VenueBooking,VenueWaitlist
from .booking_forms import VenueForm

class MapInventoryTests(TestCase):
    def setUp(self):
        self.day=timezone.localdate()+timedelta(days=1)
        self.url=reverse('campus:map-inventory')
        self.user=get_user_model().objects.create_user('never-expose-occupant')
        self.venue=Venue.objects.create(name='A座位',kind='study',building='A',floor=2)
        self.other=Venue.objects.create(name='B座位',kind='study',building='B',floor=1)
    def query(self,**changes):
        return self.client.get(self.url,{'area':'A','day':str(self.day),'slot':'14',**changes})
    def test_bookings_are_red_without_occupant_data(self):
        VenueBooking.objects.create(user=self.user,venue=self.venue,day=self.day,slot='14',request_key=uuid.uuid4())
        response=self.query();data=response.json()
        self.assertEqual(data['floors'],[2]);self.assertEqual(len(data['resources']),1)
        self.assertEqual(data['resources'][0]['state'],'booked')
        self.assertNotContains(response,'never-expose-occupant')
        self.assertNotIn('user_id',data['resources'][0]);self.assertIn('no-cache',response['Cache-Control'])
        self.assertEqual(self.query(slot='16').json()['resources'][0]['state'],'free')
    def test_held_closed_and_expired_offer(self):
        offer=VenueWaitlist.objects.create(user=self.user,venue=self.venue,day=self.day,slot='14',status='offered',offered_until=timezone.now()+timedelta(minutes=10))
        self.assertEqual(self.query().json()['resources'][0]['state'],'held')
        offer.offered_until=timezone.now()-timedelta(seconds=1);offer.save()
        self.assertEqual(self.query().json()['resources'][0]['state'],'free')
        self.venue.active=False;self.venue.save()
        self.assertEqual(self.query().json()['resources'][0]['state'],'closed')
    def test_sport_kind_and_area_isolation(self):
        table=Venue.objects.create(name='球台',kind='table_tennis',map_area='gym')
        Venue.objects.create(name='足球场',kind='football',map_area='outdoor')
        result=self.query(area='gym').json()['resources']
        self.assertEqual([r['id'] for r in result],[table.pk])
    def test_invalid_inputs_and_readonly_method(self):
        for params in [{'area':'hospital'},{'day':'broken'},{'day':str(self.day+timedelta(days=30))},{'slot':'23'}]:
            self.assertEqual(self.query(**params).status_code,400)
        self.assertEqual(self.client.post(self.url).status_code,405)
    def test_booking_link_retains_day_and_slot(self):
        data=self.query().json()['resources'][0]
        self.assertIn('slot=14',data['url']);self.assertIn(str(self.day),data['url'])
    def test_demo_initializer_keeps_reservations_and_is_idempotent(self):
        venue=Venue.objects.create(name='C 楼 · 示例 11 号座位',kind='study',building='C')
        booking=VenueBooking.objects.create(user=self.user,venue=venue,day=self.day,slot='14',request_key=uuid.uuid4())
        call_command('initialize_map_resources',stdout=StringIO());count=Venue.objects.count()
        call_command('initialize_map_resources',stdout=StringIO())
        venue.refresh_from_db();self.assertEqual(venue.floor,2)
        self.assertEqual(Venue.objects.count(),count);self.assertTrue(VenueBooking.objects.filter(pk=booking.pk,status='reserved').exists())
        self.assertEqual(Venue.objects.filter(kind='table_tennis',map_area='gym').count(),8)
        self.assertEqual(Venue.objects.filter(kind='football',map_area='outdoor').count(),1)
    def test_admin_floor_validation(self):
        form=VenueForm({'name':'测试','kind':'study','building':'A','floor':0,'map_area':'','active':True,'is_demo':True})
        self.assertFalse(form.is_valid());self.assertIn('floor',form.errors)
