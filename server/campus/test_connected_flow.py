"""Real cross-service actions, owner isolation and retries. Author: UniVerse Team."""
import json
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from 帖子.models import follow, post, profile, chat_message
from .models import CampusServicePlan, Venue, VenueBooking, SharedBooking
from .service_plans import friend_post_url
from .checkin_views import token_for
from .booking_forms import slot_start


class ConnectedFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('connected-owner')
        self.friend = User.objects.create_user('connected-friend')
        self.stranger = User.objects.create_user('connected-stranger')
        for user in (self.user, self.friend, self.stranger):
            profile.objects.create(user=user)
        follow.objects.create(user=self.user, target=self.friend)
        follow.objects.create(user=self.friend, target=self.user)
        self.client.force_login(self.user)
        self.api = reverse('campus:service-plans')
        self.day = timezone.localdate() + timedelta(days=1)
        self.venue = Venue.objects.create(name='闭环测试羽毛球场', kind='badminton', map_area='gym', floor=2)
        response = self.client.post(reverse('task-assistant-chat'), json.dumps({
            'message': '我想认识同学，然后打羽毛球'}), content_type='application/json')
        self.plan = CampusServicePlan.objects.get(pk=response.json()['plan']['id'])

    def act(self, action, **extra):
        self.plan.refresh_from_db()
        return self.client.post(self.api, json.dumps({'id': self.plan.pk,
            'revision': str(self.plan.revision), 'action': action, **extra}), content_type='application/json')

    def booked(self):
        self.assertEqual(self.act('accept').status_code, 200)
        self.assertEqual(self.act('complete').status_code, 400)
        self.plan.refresh_from_db()
        url = friend_post_url(self.plan)
        response = self.client.post(url, {'title': '找同学一起打羽毛球', 'category': '交友',
            'content': '新来学校，想认识同学一起打羽毛球。', 'tags_text': ''})
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.linked_post.author_id, self.user.pk)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(post.objects.count(), 1)
        self.assertEqual(self.act('time', day=self.day.isoformat(), slot='14').status_code, 200)
        data = self.act('book').json()['assistant']
        payload = {'draft_key': data['draft_key'], 'venue_id': self.venue.pk}
        response = self.client.post(reverse('task-assistant-confirm'), json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.state, 'active')
        self.assertEqual(response.json()['plan']['current'], 'share')
        self.assertEqual(chat_message.objects.count(), 0)
        self.assertIsNotNone(self.plan.booking.checkin_deadline)
        # Browser retries cannot add a second reservation or finish later steps.
        self.client.post(reverse('task-assistant-confirm'), json.dumps(payload), content_type='application/json')
        self.assertEqual(VenueBooking.objects.count(), 1)
        return self.plan.booking

    def share(self):
        data = self.client.get(self.api).json()['plan']
        url = next(step['url'] for step in data['steps'] if step['key'] == 'share')
        response = self.client.post(url, {'action': 'share', 'share_kind': 'booking',
            'friend': self.friend.pk, 'resource': self.plan.booking_id})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/assistant/', response.url)
        return url

    def test_publish_book_share_route_checkin_and_relogin(self):
        booking = self.booked()
        url = self.share()
        self.assertEqual(SharedBooking.objects.count(), 1)
        self.assertEqual(self.client.post(url, {'action': 'share', 'share_kind': 'booking',
            'friend': self.friend.pk, 'resource': booking.pk}).status_code, 404)
        self.assertEqual(chat_message.objects.count(), 1)
        plan = self.client.get(self.api).json()['plan']
        self.assertEqual(plan['current'], 'navigate')
        route = next(step['url'] for step in plan['steps'] if step['key'] == 'navigate')
        page = self.client.get(route)
        self.assertContains(page, 'plan_navigation')
        self.assertEqual(self.client.get(self.api).json()['plan']['current'], 'navigate')
        self.assertEqual(self.act('navigated').json()['plan']['current'], 'checkin')
        self.client.logout()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.api).json()['plan']['current'], 'checkin')
        url = reverse('campus:booking-checkin', args=[booking.pk])
        with patch('django.utils.timezone.now', return_value=slot_start(self.day, '14')):
            self.assertEqual(self.client.post(url, {'token': token_for(booking)}).status_code, 302)
        final = self.client.get(self.api).json()['plan']
        self.assertEqual(final['state'], 'completed')
        self.assertEqual(final['progress'], 6)
        self.assertEqual(final['steps'][-1]['evidence']['label'], '已签到')

    def test_no_false_arrival_and_optional_steps_are_explicit(self):
        booking = self.booked()
        self.assertEqual(self.act('navigated').status_code, 400)
        self.assertEqual(self.act('skip').json()['plan']['current'], 'navigate')
        self.assertEqual(self.act('skip').json()['plan']['current'], 'checkin')
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.skipped, ['share', 'navigate'])
        self.assertIsNone(self.plan.shared_message_id)
        self.assertIsNone(self.plan.navigation_started_at)
        self.assertEqual(self.act('complete').status_code, 400)
        url = reverse('campus:booking-checkin', args=[booking.pk])
        self.assertEqual(self.client.post(url, {'token': token_for(booking)}).status_code, 200)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.state, 'active')

    def test_foreign_resource_and_stranger_cannot_advance_or_receive(self):
        self.booked()
        data = self.client.get(self.api).json()['plan']
        url = next(step['url'] for step in data['steps'] if step['key'] == 'share')
        payload = {'action': 'share', 'share_kind': 'booking', 'friend': self.stranger.pk, 'resource': self.plan.booking_id}
        self.assertEqual(self.client.post(url, payload).status_code, 404)
        second = Venue.objects.create(name='其他场地', kind='badminton')
        other = VenueBooking.objects.create(user=self.user, venue=second, day=self.day, slot='16', request_key=uuid.uuid4())
        self.assertEqual(self.client.post(url, {**payload, 'friend': self.friend.pk, 'resource': other.pk}).status_code, 400)
        self.assertEqual(chat_message.objects.count(), 0)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(url).status_code, 200)  # Hub itself is public to logged-in owners.
        self.assertIsNone(self.client.get(self.api).json()['plan'])
        self.assertEqual(self.act('skip').status_code, 404)

    def test_release_returns_to_time_without_losing_published_post(self):
        booking = self.booked()
        booking.status = 'no_show'; booking.save(update_fields=['status'])
        self.assertTrue(self.client.get(self.api).json()['plan']['blocked'])
        self.assertEqual(self.act('skip').status_code, 400)
        data = self.act('rebook').json()['plan']
        self.assertEqual(data['current'], 'time')
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.linked_post_id)
        self.assertIsNone(self.plan.booking_id)
        booking.refresh_from_db(); self.assertEqual(booking.status, 'no_show')

    def test_home_continue_and_forum_use_same_social_window(self):
        self.act('accept')
        self.assertEqual(self.client.get(reverse('campus:home-agenda')).json()['plan']['id'], self.plan.pk)
        response = self.client.get(reverse('campus:home'))
        self.assertContains(response, 'data-social-window')
        self.assertContains(response, 'data-hub="/friends/"')
        self.assertEqual(self.client.get(reverse('campus:friend-hub'))['X-Frame-Options'],'SAMEORIGIN')
        self.assertNotContains(response, 'src="/static/friends.js"')

    def test_resume_after_real_checkin_does_not_get_stuck(self):
        booking = self.booked()
        self.act('skip'); self.act('skip'); self.act('cancel')
        from .attendance import check_in
        with patch('django.utils.timezone.now', return_value=slot_start(self.day, '14')):
            self.assertEqual(check_in(self.user, booking.pk)[1], 'ok')
        self.plan.refresh_from_db(); self.assertEqual(self.plan.state, 'cancelled')
        self.assertEqual(self.act('resume').json()['plan']['state'], 'completed')

    def test_pending_migration_preserves_progress_and_completed_history(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        self.plan.steps = ['friends', 'time', 'booking']
        self.plan.completed = ['friends']; self.plan.workflow_version = 1
        self.plan.save()
        old = CampusServicePlan.objects.create(user=self.friend, source='old',
            steps=['time', 'booking'], completed=['time', 'booking'], state='completed')
        migration = import_module('campus.migrations.0018_connected_service_plan')
        migration.upgrade_pending_plans(apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))
        self.plan.refresh_from_db(); old.refresh_from_db()
        self.assertEqual(self.plan.completed, ['friends'])
        self.assertEqual(self.plan.steps[-3:], ['share', 'navigate', 'checkin'])
        self.assertEqual(old.steps, ['time', 'booking'])
        self.assertEqual(old.workflow_version, 1)
