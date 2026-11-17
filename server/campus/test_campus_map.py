from django.test import TestCase
from django.urls import reverse
from .models import Venue

class CampusMapTests(TestCase):
    def test_public_page_aggregates_only_active_resources(self):
        before=Venue.objects.filter(kind='study',active=True).count()
        Venue.objects.create(name='internal venue label',kind='study',active=True)
        Venue.objects.create(name='disabled venue',kind='study',active=False)
        response=self.client.get(reverse('campus:campus-map'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['map_data']['counts']['study'],before+1)
        self.assertNotContains(response,'internal venue label')
        self.assertNotContains(response,'disabled venue')
        self.assertContains(response,'campus-map-canvas')
        self.assertIn('no-cache',response['Cache-Control'])
        self.assertEqual(self.client.post(reverse('campus:campus-map')).status_code,405)
    def test_russian_ui_and_local_assets(self):
        session=self.client.session;session['campus_language']='ru';session.save()
        response=self.client.get(reverse('campus:campus-map'))
        self.assertContains(response,'3D-карта кампуса')
        self.assertContains(response,'/static/campus/campus-map.js')
