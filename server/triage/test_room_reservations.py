import json
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from accounts.models import Profile
from .models import RoomAppointment


class RoomReservationTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 16, 9, 30, tzinfo=ZoneInfo('Asia/Shanghai'))
        self.clock = patch('triage.room_reservations.timezone.now', return_value=self.now)
        self.clock.start();self.addCleanup(self.clock.stop)
        self.user = self.patient('appointment_patient')
        self.client.force_login(self.user)

    def patient(self, name):
        user = User.objects.create_user(name)
        Profile.objects.create(user=user, full_name='预约测试', gender='other')
        return user

    def payload(self, **changes):
        return {'room':'room1', 'start':self.now.replace(hour=10, minute=0).isoformat(), 'request_key':str(uuid.uuid4()), **changes}

    def book(self, payload=None):
        return self.client.post('/api/rooms/reserve/',json.dumps(payload or self.payload()),content_type='application/json')

    def test_date_window_and_future_clinic_after_evening(self):
        response = self.client.get('/api/rooms/?date=2026-10-19')
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json()['dates']),4)
        self.assertEqual(response.json()['max_date'],'2026-10-19')
        for day in ('2026-10-15','2026-10-20','not-a-date'):
            self.assertEqual(self.client.get('/api/rooms/',{'date':day}).status_code,400)
        self.assertEqual(self.book(self.payload(start='2026-10-19T10:00:00+08:00')).status_code,201)
        self.assertEqual(self.book(self.payload(start='2026-10-20T10:00:00+08:00')).status_code,400)
        with patch('triage.room_reservations.local_now',return_value=self.now.replace(hour=20)):
            future=self.client.get('/api/rooms/?date=2026-10-17').json()
            self.assertEqual(len(future['rooms'][0]['slots']),7)
            today=self.client.get('/api/rooms/').json()
            self.assertFalse(today['rooms'][0]['available'])
            self.assertTrue(today['rooms'][3]['available'])

    def test_rejects_past_break_and_after_17_slots(self):
        for start in ('2026-10-16T09:00:00+08:00','2026-10-16T12:00:00+08:00','2026-10-16T17:00:00+08:00','2026-10-17T17:00:00+08:00','2026-10-17T10:30:00+08:00','2026-10-17T10:00:00','0001-01-01T00:00:00+14:00'):
            self.assertEqual(self.book(self.payload(start=start)).status_code,400,start)
        self.assertFalse(RoomAppointment.objects.exists())

    def test_emergency_and_assistance_are_not_bookable(self):
        for room in ('emergency1','emergency2','special'):
            self.assertEqual(self.book(self.payload(room=room)).status_code,400)
        data=self.client.get('/api/rooms/').json()
        for room in data['rooms'][3:5]:
            self.assertTrue(room['available'])
            self.assertFalse(room['requires_booking'])
            self.assertEqual(room['slots'],[])

    def test_idempotency_and_cross_room_conflict(self):
        data=self.payload()
        first=self.book(data);again=self.book(data)
        self.assertEqual(first.status_code,201)
        self.assertEqual(again.status_code,200)
        self.assertEqual(first.json()['appointment']['id'],again.json()['appointment']['id'])
        self.assertEqual(self.book({**data,'room':'room2'}).status_code,409)
        self.assertEqual(self.book(self.payload(room='room2')).status_code,409)
        self.assertEqual(RoomAppointment.objects.count(),1)

    def test_capacity_remaining_and_cancel_release(self):
        for i in range(5):
            self.client.force_login(self.patient(f'capacity_{i}'))
            self.assertEqual(self.book().status_code,201)
        self.client.force_login(self.user)
        self.assertEqual(self.book().status_code,409)
        slot=next(s for s in self.client.get('/api/rooms/').json()['rooms'][0]['slots'] if s['label'].startswith('10:00'))
        self.assertEqual(slot['remaining'],0)
        record=RoomAppointment.objects.first()
        self.client.force_login(record.user)
        self.assertEqual(self.client.post(f'/api/rooms/{record.pk}/cancel/').status_code,200)
        self.client.force_login(self.user)
        self.assertEqual(self.book().status_code,201)
        self.assertEqual(RoomAppointment.objects.filter(status='confirmed').count(),5)

    def test_cancel_ownership_and_started_appointment(self):
        record=self.book().json()['appointment']
        other=self.patient('other_booking_patient');self.client.force_login(other)
        self.assertEqual(self.client.post(f'/api/rooms/{record["id"]}/cancel/').status_code,404)
        self.assertEqual(self.client.get('/api/rooms/mine/').json()['appointments'],[])
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f'/api/rooms/{record["id"]}/cancel/').status_code,405)
        with patch('triage.room_reservations.timezone.now',return_value=self.now.replace(hour=10,minute=0)):
            self.assertEqual(self.client.post(f'/api/rooms/{record["id"]}/cancel/').status_code,409)

    def test_authentication_csrf_and_validation(self):
        anonymous=Client()
        self.assertEqual(anonymous.get('/api/rooms/').status_code,401)
        self.assertEqual(anonymous.get('/api/rooms/mine/').status_code,401)
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.user)
        self.assertEqual(secure.post('/api/rooms/reserve/',json.dumps(self.payload()),content_type='application/json').status_code,403)
        for body in ('[]','{}','null','not json'):
            self.assertEqual(self.client.post('/api/rooms/reserve/',body,content_type='application/json').status_code,400)

    def test_database_protects_capacity_and_double_booking(self):
        self.book();record=RoomAppointment.objects.get()
        with self.assertRaises(IntegrityError),transaction.atomic():
            RoomAppointment.objects.create(user=self.patient('constraint_patient'),room=record.room,starts_at=record.starts_at,ends_at=record.ends_at,number=record.number,request_key=uuid.uuid4())
        with self.assertRaises(IntegrityError),transaction.atomic():
            RoomAppointment.objects.create(user=self.user,room='room2',starts_at=record.starts_at,ends_at=record.ends_at,number=2,request_key=uuid.uuid4())


class JapaneseInterfaceTests(TestCase):
    def test_switch_persists_and_auth_pages_are_japanese(self):
        response=self.client.post('/language/',{'language':'ja','next':'/'})
        self.assertEqual(response.status_code,302)
        home=self.client.get('/')
        self.assertContains(home,'lang="ja"')
        self.assertContains(home,'晴空キャンパス')
        self.assertContains(home,'日本語')
        self.assertEqual(home['Content-Language'],'ja')
        login=self.client.get('/login/guide/')
        self.assertContains(login,'アカウント')
        self.assertContains(login,'パスワード')

    def test_all_fixed_catalog_entries_have_japanese(self):
        from campus.ui_language import TRANSLATIONS
        self.assertTrue(all(item.get('ja') for item in TRANSLATIONS.values()))
