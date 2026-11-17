import json
import uuid
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.cache import cache
from accounts.models import Profile
from .models import Consultation
from .test_doctors import report


class CareChoiceTests(TestCase):
    def setUp(self):
        cache.clear()
        user = User.objects.create_user('care_choice_patient')
        Profile.objects.create(user=user, full_name='测试用户', gender='other', age=20)
        self.client.force_login(user)
        self.payload = {'accepted_notice': True, 'part': 'left_leg', 'detail': '膝盖',
            'description': '左膝盖疼了两天', 'duration': '两天', 'feeling': 'mild',
            'request_key': str(uuid.uuid4()), 'preview': True}

    def send(self, **changes):
        return self.client.post('/api/advanced/assess/', json.dumps({**self.payload, **changes}), content_type='application/json')

    @patch('triage.views.create_report', return_value=report())
    def test_preview_never_creates_doctor_consultation(self, generate):
        response = self.send()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['queued'])
        self.assertIn('report', response.json())
        self.assertFalse(Consultation.objects.exists())

    @patch('triage.views.create_report', return_value=report())
    def test_online_choice_submits_once_and_reuses_server_report(self, generate):
        self.send()
        first = self.send(preview=False, report={'summary': 'Untrusted browser text'})
        again = self.send(preview=False)
        self.assertTrue(first.json()['queued'])
        self.assertEqual(first.json()['code'], again.json()['code'])
        self.assertEqual(Consultation.objects.count(), 1)
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(Consultation.objects.get().ai_report['summary'], '左膝盖隐痛')

    @patch('triage.views.create_report', return_value=report())
    def test_changed_description_cannot_reuse_old_report(self, generate):
        self.send()
        self.send(description='左膝盖疼了三天')
        self.assertEqual(generate.call_count, 2)
        self.assertFalse(Consultation.objects.exists())

    def test_invalid_preview_does_not_submit(self):
        self.assertEqual(self.send(preview='true').status_code, 400)
        self.assertFalse(Consultation.objects.exists())
