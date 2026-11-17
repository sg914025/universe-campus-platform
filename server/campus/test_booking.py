import uuid
from datetime import timedelta
from django.contrib.auth.models import User,Group,Permission
from django.db import IntegrityError,transaction
from django.test import TestCase,Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import Profile
from triage.models import DoctorProfile,Department
from .models import Venue,VenueBooking

class VenueBookingTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('venue_test',password='Sturdy-Mint!73')
        Profile.objects.create(user=self.user,full_name='场地测试同学',gender='female',age=20)
        self.other=User.objects.create_user('other_venue_test',password='Sturdy-Mint!73')
        self.venue=Venue.objects.filter(kind='study').first()
        self.day=timezone.localdate()+timedelta(days=1)
        self.data={'day':self.day.isoformat(),'slot':'14','request_key':str(uuid.uuid4())}
        self.url=reverse('campus:booking-venue',args=[self.venue.pk])
        self.client.force_login(self.user)

    def test_home_has_fourth_entrance_and_forum_still_has_no_errand_tab(self):
        self.assertContains(self.client.get(reverse('home')),'/booking/')
        self.assertContains(self.client.get(reverse('campus:booking')),'自习室')
        self.assertNotContains(self.client.get(reverse('campus:home')),'href="/errands/"')

    def test_save_and_duplicate_submission_only_create_one_booking(self):
        self.assertRedirects(self.client.post(self.url,self.data),reverse('campus:booking-mine'))
        self.assertRedirects(self.client.post(self.url,self.data),reverse('campus:booking-mine'))
        self.assertEqual(VenueBooking.objects.count(),1)
        self.assertEqual(VenueBooking.objects.get().user_id,self.user.pk)
        self.assertContains(self.client.get(reverse('campus:booking-mine')),'已预约')

    def test_same_resource_or_same_user_time_cannot_be_reserved_twice(self):
        self.client.post(self.url,self.data)
        self.client.force_login(self.other)
        response=self.client.post(self.url,{**self.data,'request_key':str(uuid.uuid4())})
        self.assertContains(response,'该时段刚被预约')
        self.client.force_login(self.user)
        other=Venue.objects.exclude(pk=self.venue.pk).first()
        response=self.client.post(reverse('campus:booking-venue',args=[other.pk]),{**self.data,'request_key':str(uuid.uuid4())})
        self.assertContains(response,'你已有同时段预约')
        self.assertEqual(VenueBooking.objects.count(),1)

    def test_database_constraint_prevents_overbooking_even_without_form(self):
        VenueBooking.objects.create(venue=self.venue,user=self.user,day=self.day,slot='14',request_key=uuid.uuid4())
        with self.assertRaises(IntegrityError),transaction.atomic():
            VenueBooking.objects.create(venue=self.venue,user=self.other,day=self.day,slot='14',request_key=uuid.uuid4())

    def test_cancel_is_owner_only_and_releases_slot(self):
        self.client.post(self.url,self.data);booking=VenueBooking.objects.get()
        cancel=reverse('campus:booking-cancel',args=[booking.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(cancel).status_code,404)
        self.assertNotContains(self.client.get(reverse('campus:booking-mine')),self.venue.name)
        self.client.force_login(self.user);self.client.post(cancel)
        booking.refresh_from_db();self.assertEqual(booking.status,'cancelled')
        self.client.force_login(self.other);self.client.post(self.url,{**self.data,'request_key':str(uuid.uuid4())})
        self.assertEqual(VenueBooking.objects.filter(status='reserved').get().user_id,self.other.pk)

    def test_invalid_dates_slots_and_request_keys_do_not_create_record(self):
        for change in ({'day':(timezone.localdate()-timedelta(days=1)).isoformat()},{'day':(timezone.localdate()+timedelta(days=15)).isoformat()},{'slot':'99'},{'request_key':'bad'},{'day':'bad'}):
            self.assertEqual(self.client.post(self.url,{**self.data,**change}).status_code,200)
        self.assertFalse(VenueBooking.objects.exists())
        self.venue.active=False;self.venue.save()
        self.assertEqual(self.client.post(self.url,self.data).status_code,404)

    def test_past_started_booking_cannot_be_cancelled(self):
        booking=VenueBooking.objects.create(venue=self.venue,user=self.user,day=timezone.localdate()-timedelta(days=1),slot='14',request_key=uuid.uuid4())
        self.client.post(reverse('campus:booking-cancel',args=[booking.pk]))
        booking.refresh_from_db();self.assertEqual(booking.status,'reserved')

    def test_guest_and_csrf_checks_cannot_be_bypassed(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url,self.data).status_code,302)
        self.assertFalse(VenueBooking.objects.exists())
        protected=Client(enforce_csrf_checks=True);protected.force_login(self.user)
        self.assertEqual(protected.post(self.url,self.data).status_code,403)
        self.assertEqual(self.client.get(reverse('campus:booking-cancel',args=[1])).status_code,302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('campus:booking-cancel',args=[1])).status_code,405)

    def test_booking_manager_can_manage_but_doctor_and_student_cannot(self):
        endpoint=reverse('campus:booking-admin')
        self.assertEqual(self.client.get(endpoint).status_code,403)
        DoctorProfile.objects.create(user=self.user,department=Department.objects.get(slug='bone'),display_name='测试医生')
        self.assertEqual(self.client.get(endpoint).status_code,403)
        group=Group.objects.create(name='booking_test_managers')
        group.permissions.add(Permission.objects.get(content_type__app_label='campus',codename='manage_bookings'))
        self.other.groups.add(group);self.client.force_login(self.other)
        self.assertEqual(self.client.get(endpoint).status_code,200)
        response=self.client.post(endpoint,{'name':'新测试场地','kind':'badminton','active':'on','is_demo':'on'})
        self.assertEqual(response.status_code,302)
        self.assertTrue(Venue.objects.filter(name='新测试场地').exists())

    def test_available_count_changes_after_reserving(self):
        response=self.client.get(reverse('campus:booking'),{'day':self.day.isoformat(),'kind':'study','building':'other'})
        self.assertContains(response,'5 个时段可预约')
        self.client.post(self.url,self.data)
        response=self.client.get(self.url,{'day':self.day.isoformat()})
        self.assertContains(response,'已被预约')
        self.assertNotContains(response,self.user.username)
