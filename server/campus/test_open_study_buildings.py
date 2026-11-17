from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from .models import Venue


class OpenStudyBuildingsTests(TestCase):
    def test_all_buildings_open_and_repeat_is_safe(self):
        existing=Venue.objects.create(name='旧座位',kind='study',active=False)
        call_command('open_study_buildings',stdout=StringIO())
        for building in ('A','B','C','library'):
            self.assertEqual(Venue.objects.filter(kind='study',building=building,active=True).count(),20)
        existing.refresh_from_db()
        self.assertTrue(existing.active)
        count=Venue.objects.count()
        call_command('open_study_buildings',stdout=StringIO())
        self.assertEqual(Venue.objects.count(),count)
