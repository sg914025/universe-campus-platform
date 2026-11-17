import uuid
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from .models import Venue,VenueBooking

class HomeAgendaTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_user('agenda_owner')
        self.other=User.objects.create_user('agenda_other')
        self.venue=Venue.objects.create(name='真实场地原名',kind='study',location='图书馆')
        self.day=timezone.localdate()+timedelta(days=1)
        self.item=VenueBooking.objects.create(user=self.owner,venue=self.venue,day=self.day,slot='14',request_key=uuid.uuid4())
        self.url=reverse('campus:home-agenda')
        self.client.force_login(self.owner)

    def test_owner_only_and_private_cache(self):
        VenueBooking.objects.create(user=self.other,venue=self.venue,day=self.day,slot='16',request_key=uuid.uuid4())
        response=self.client.get(self.url,{'month':self.day.strftime('%Y-%m')})
        self.assertEqual([x['id'] for x in response.json()['events']],[self.item.pk])
        self.assertEqual([x['id'] for x in response.json()['cards']],[self.item.pk])
        self.assertIn('no-store',response['Cache-Control'])
        self.assertNotContains(response,'agenda_other')

    def test_cancelled_visible_in_calendar_not_upcoming(self):
        self.item.status='cancelled';self.item.save()
        data=self.client.get(self.url,{'month':self.day.strftime('%Y-%m')}).json()
        self.assertEqual(data['cards'],[])
        self.assertFalse(data['events'][0]['active'])

    def test_bad_month_and_read_only(self):
        for month in ('2026-13','garbage','1999-01','2026-1'):
            self.assertEqual(self.client.get(self.url,{'month':month}).status_code,400)
        self.assertEqual(self.client.post(self.url).status_code,405)
        self.assertEqual(VenueBooking.objects.count(),1)

    def test_russian_keeps_original_venue(self):
        session=self.client.session;session['campus_language']='ru';session.save()
        item=self.client.get(self.url,{'month':self.day.strftime('%Y-%m')}).json()['events'][0]
        self.assertEqual(item['name'],self.venue.name)
        self.assertNotEqual(item['status'],'已预约')
        self.assertEqual(item['url'],reverse('campus:service-card',args=[self.item.pk]))

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code,302)
