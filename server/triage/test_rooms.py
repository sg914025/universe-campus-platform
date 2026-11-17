from datetime import datetime
from zoneinfo import ZoneInfo
from django.test import SimpleTestCase, TestCase
from .rooms import room_status


class RoomHoursTests(SimpleTestCase):
    def test_exact_closing_boundary(self):
        zone = ZoneInfo('Asia/Shanghai')
        before = room_status(datetime(2026, 10, 15, 16, 59, 59, tzinfo=zone))
        after = room_status(datetime(2026, 10, 15, 17, 0, tzinfo=zone))
        self.assertEqual(len(before['rooms']), 6)
        self.assertTrue(all(r['available'] for r in before['rooms']))
        self.assertEqual([r['name'] for r in after['rooms'] if r['available']], ['急诊1', '急诊2'])

    def test_uses_shanghai_not_caller_timezone(self):
        state = room_status(datetime(2026, 10, 15, 9, tzinfo=ZoneInfo('UTC')))
        self.assertTrue(state['after_hours'])


class RoomAccessTests(TestCase):
    def test_anonymous_denied(self):
        self.assertEqual(self.client.get('/api/rooms/').status_code, 401)

    def test_complete_patient_can_read_status(self):
        from django.contrib.auth.models import User
        from accounts.models import Profile
        user = User.objects.create_user('rooms_patient')
        Profile.objects.create(user=user, full_name='测试用户', gender='other')
        self.client.force_login(user)
        response = self.client.get('/api/rooms/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['rooms']), 6)
        self.assertIn('no-store', response['Cache-Control'])
