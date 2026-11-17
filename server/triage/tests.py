import json
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Profile
from .models import Consultation
from .parts import find_part


class AdvancedTriageTests(TestCase):
    def setUp(self):
        from .test_doctors import report
        self.report_mock=patch('triage.views.create_report',return_value=report()).start()
        self.addCleanup(patch.stopall)
        self.user = User.objects.create_user('patient_one', password='Sturdy-Mint!73')
        Profile.objects.create(user=self.user, full_name='测试用户', gender='female', age=28)
        self.client.force_login(self.user)

    def payload(self, **changes):
        data = {'accepted_notice': True, 'part': 'left_leg', 'detail': '膝盖', 'description': '左膝盖疼了两天，走路时明显。',
                'duration': '两天', 'feeling': 'mild', 'request_key': str(uuid.uuid4())}
        data.update(changes)
        return data

    def assess(self, **changes):
        return self.client.post(reverse('advanced-assess'), json.dumps(self.payload(**changes)), content_type='application/json')

    def test_normal_confirmed_analysis_is_auto_submitted(self):
        response = self.assess()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['queued'])
        self.assertEqual(Consultation.objects.count(), 1)

    def test_high_description_is_saved_in_doctor_queue(self):
        response = self.assess(feeling='severe')
        self.assertTrue(response.json()['queued'])
        record = Consultation.objects.get()
        self.assertEqual(record.user, self.user)
        self.assertEqual(record.part, 'left_leg')
        self.assertEqual(record.status, 'pending')
        self.assertEqual(record.doctor_reply, '')

    def test_emergency_shows_immediate_help_and_never_says_to_wait(self):
        response = self.assess(part='chest', detail='', description='胸痛并且呼吸困难')
        data = response.json()
        self.assertTrue(data['emergency'])
        self.assertTrue(data['queued'])
        self.assertIn('120', data['urgent_message'])
        self.assertIn('不要等待', data['urgent_message'])

    def test_duplicate_request_does_not_create_duplicate_queue_records(self):
        payload = self.payload(feeling='severe')
        responses = [self.client.post(reverse('advanced-assess'), json.dumps(payload), content_type='application/json') for _ in range(2)]
        self.assertEqual(responses[0].json()['code'], responses[1].json()['code'])
        self.assertEqual(Consultation.objects.count(), 1)

    def test_missing_notice_invalid_part_description_and_format_are_rejected(self):
        for data in ({'accepted_notice': False}, {'part': 'unknown'}, {'detail': '不存在的位置'},
                     {'description': ''}, {'description': 'a' * 2001}, {'feeling': 'invalid'},
                     {'request_key': 'invalid'}, {'description': ['invalid']}):
            with self.subTest(data=data):
                self.assertEqual(self.assess(**data).status_code, 400)
        self.assertEqual(self.client.post(reverse('advanced-assess'), '[]', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post(reverse('advanced-assess'), '{', content_type='application/json').status_code, 400)
        self.assertEqual(Consultation.objects.count(), 0)

    def test_inbox_and_read_reply_only_allow_record_owner(self):
        self.assess(feeling='severe')
        own = Consultation.objects.get()
        other = User.objects.create_user('patient_two', password='Sturdy-Mint!73')
        foreign = Consultation.objects.create(user=other, request_key=uuid.uuid4(), part='head', description='别人的咨询', feeling='severe', level='high')
        records = self.client.get(reverse('inbox')).json()['messages']
        self.assertEqual([record['id'] for record in records], [own.pk])
        self.assertEqual(self.client.post(reverse('read-reply', args=[foreign.pk])).status_code, 404)

    def test_logged_out_and_incomplete_profiles_cannot_use_apis(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('inbox')).status_code, 401)
        self.assertEqual(self.assess().status_code, 401)
        Profile.objects.filter(user=self.user).delete()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('inbox')).status_code, 403)
        self.assertEqual(self.assess().status_code, 403)

    def test_doctor_admin_reply_appears_in_inbox_and_can_be_marked_read(self):
        self.assess(feeling='severe')
        record = Consultation.objects.get()
        doctor = User.objects.create_superuser('doctor_test', 'doctor@example.test', 'Sturdy-Mint!73')
        doctor_client = Client()
        doctor_client.force_login(doctor)
        response = doctor_client.post(reverse('admin:triage_consultation_change', args=[record.pk]), {'doctor_reply': '测试回复：请到实际医院咨询医护。', '_save': '保存'})
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, 'replied')
        self.assertEqual(record.replied_by, doctor)
        self.assertIsNotNone(record.replied_at)
        inbox = self.client.get(reverse('inbox')).json()
        self.assertEqual(inbox['unread'], 1)
        self.assertIn('测试回复', inbox['messages'][0]['reply'])
        self.client.post(reverse('read-reply', args=[record.pk]))
        self.assertEqual(self.client.get(reverse('inbox')).json()['unread'], 0)

    def test_csrf_is_required_and_normal_user_cannot_access_doctor_backend(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        payload = json.dumps(self.payload(feeling='severe'))
        self.assertEqual(client.post(reverse('advanced-assess'), payload, content_type='application/json').status_code, 403)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/system-admin/login/', response.url)

    def test_body_keywords_recognize_sides_and_keep_unspecified_side_unknown(self):
        for text, part in [('左手腕疼', 'left_hand'), ('右膝盖不舒服', 'right_leg'), ('肚子痛', 'abdomen'),
                           ('腰疼', 'back'), ('肩膀痛', 'arms'), ('膝盖痛', 'legs'), ('不舒服', None)]:
            with self.subTest(text=text):
                self.assertEqual(find_part(text), part)
