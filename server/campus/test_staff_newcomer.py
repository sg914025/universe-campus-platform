import json,uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User,Permission
from django.test import TestCase,Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import Profile
from triage.models import Department,DoctorProfile,Consultation
from 帖子.models import post,report
from 跑腿.models import question
from .models import StaffAuditEvent,Venue


class StaffNewcomerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root=User.objects.create_superuser('flow_root',password='Preview-Only!2386')
        cls.student=User.objects.create_user('flow_student')
        Profile.objects.create(user=cls.student,full_name='测试同学',gender='other')
        cls.manager=User.objects.create_user('flow_manager')
        cls.manager.user_permissions.add(Permission.objects.get(codename='manage_campus',content_type__app_label='campus'))
        cls.booking=User.objects.create_user('flow_booking')
        cls.booking.user_permissions.add(Permission.objects.get(codename='manage_bookings',content_type__app_label='campus'))
        cls.doctor_user=User.objects.create_user('flow_doctor')
        cls.department=Department.objects.get(slug='bone')
        DoctorProfile.objects.create(user=cls.doctor_user,department=cls.department,display_name='测试医生')
        cls.case=Consultation.objects.create(user=cls.student,department=cls.department,request_key=uuid.uuid4(),part='head',description='SECRET MEDICAL TEXT',feeling='mild',level='low')

    def test_overview_and_logs_are_superadmin_only(self):
        for user in (self.student,self.manager,self.booking,self.doctor_user):
            self.client.force_login(user)
            for name in ('staff-overview','staff-audit'):
                self.assertEqual(self.client.get(reverse(name)).status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('staff-overview')).status_code,302)
        self.client.force_login(self.root)
        response=self.client.get(reverse('staff-overview'))
        self.assertContains(response,'运营总览')
        self.assertNotContains(response,'SECRET MEDICAL TEXT')
        self.assertNotContains(response,reverse('doctor-case',args=[self.case.pk]))
        self.assertContains(response,'医生待回复')
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertEqual(self.client.post(reverse('staff-overview')).status_code,405)

    def test_doctor_reply_logged_without_medical_text(self):
        self.client.force_login(self.doctor_user)
        response=self.client.post(reverse('doctor-reply',args=[self.case.pk]),{'content':'SECRET DOCTOR REPLY'})
        self.assertEqual(response.status_code,302)
        event=StaffAuditEvent.objects.get()
        self.assertEqual(event.actor,self.doctor_user)
        self.assertEqual(event.before_state,{'status':'pending'})
        self.assertEqual(event.after_state,{'status':'replied'})
        self.assertNotIn('SECRET',json.dumps(event.__dict__,default=str))
        self.assertEqual(event.action,'回复导诊咨询')

    def test_invalid_or_wrong_department_reply_not_logged(self):
        self.client.force_login(self.doctor_user)
        self.client.post(reverse('doctor-reply',args=[self.case.pk]),{'content':''})
        other=Department.objects.exclude(pk=self.department.pk).first()
        self.case.department=other;self.case.save(update_fields=['department'])
        self.assertEqual(self.client.post(reverse('doctor-reply',args=[self.case.pk]),{'content':'no'}).status_code,404)
        self.assertFalse(StaffAuditEvent.objects.exists())

    def test_bulk_review_update_is_logged_and_repeat_is_not(self):
        item=post.objects.create(author=self.student,title='test',content='SECRET POST')
        complaint=report.objects.create(user=self.student,post=item,title='test',content='SECRET REPORT',reason='SECRET REASON')
        self.client.force_login(self.manager)
        self.client.post(reverse('campus:review_report',args=[complaint.pk]),{'action':'hide','note':'SECRET NOTE'})
        event=StaffAuditEvent.objects.get()
        self.assertEqual(event.after_state,{'status':'hidden'})
        self.assertNotIn('SECRET',json.dumps(event.__dict__,default=str))
        item.refresh_from_db();self.assertTrue(item.is_hidden)
        self.client.post(reverse('campus:review_report',args=[complaint.pk]),{'action':'hide'})
        self.assertEqual(StaffAuditEvent.objects.count(),1)

    def test_booking_create_and_edit_have_trace(self):
        self.client.force_login(self.booking)
        payload={'name':'测试场地','kind':'study','active':'on','is_demo':'on','description':'SECRET DESCRIPTION'}
        self.client.post(reverse('campus:booking-admin'),payload)
        venue=Venue.objects.get(name='测试场地')
        self.assertEqual(StaffAuditEvent.objects.get().action,'新增场地')
        payload['name']='新场地名';payload.pop('active')
        self.client.post(reverse('campus:booking-venue-edit',args=[venue.pk]),payload)
        event=StaffAuditEvent.objects.first()
        self.assertEqual(event.before_state['active'],True)
        self.assertEqual(event.after_state['active'],False)
        self.assertIn('name',event.changed_fields)
        self.assertNotIn('SECRET',json.dumps(event.__dict__,default=str))

    def test_staff_creation_logged_without_password_or_new_access(self):
        self.client.force_login(self.root)
        password='Preview-Created!987'
        self.client.post(reverse('management-accounts'),{'username':'created_flow_manager','full_name':'测试管理','role':'campus','password1':password,'password2':password})
        created=User.objects.get(username='created_flow_manager')
        event=StaffAuditEvent.objects.get(action='创建管理账号')
        self.assertEqual(event.target,f'auth.user:{created.pk}')
        self.assertNotIn(password,json.dumps(event.__dict__,default=str))
        self.assertFalse(created.is_superuser)

    def test_audit_failure_rolls_back_change(self):
        self.client.force_login(self.doctor_user)
        with patch('campus.audit.record_event',side_effect=RuntimeError('audit write failed')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('doctor-reply',args=[self.case.pk]),{'content':'should roll back'})
        self.case.refresh_from_db();self.assertEqual(self.case.status,'pending');self.assertEqual(self.case.doctor_reply,'')

    def test_audit_filter_and_safe_render(self):
        StaffAuditEvent.objects.create(actor=self.root,actor_name='<script>alert(1)</script>',module='superadmin',action='创建管理账号',target='auth.user:123')
        self.client.force_login(self.root)
        response=self.client.get(reverse('staff-audit'))
        self.assertContains(response,'&lt;script&gt;')
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertEqual(len(self.client.get(reverse('staff-audit'),{'module':'doctor'}).context['page']),0)

    def test_pending_summary_has_24_hour_reminder_without_patient_records(self):
        Consultation.objects.filter(pk=self.case.pk).update(created_at=timezone.now()-timedelta(hours=25))
        question.objects.create(user=self.student,content='SECRET QUESTION')
        self.client.force_login(self.root)
        response=self.client.get(reverse('staff-overview'))
        self.assertEqual(response.context['overdue_health'],1)
        self.assertEqual(response.context['overdue_questions'],0)
        self.assertNotContains(response,'SECRET')

    def test_newcomer_public_four_languages_and_all_destinations(self):
        for lang,title in [('zh','新生校园向导'),('en','New student guide'),('ru','Путеводитель первокурсника'),('ja','新入生ガイド')]:
            self.client.cookies['campus_language']=lang
            response=self.client.get(reverse('welcome'))
            self.assertContains(response,title)
            for destination in ('campus:friends','campus:errand_create','campus:booking','guide'):
                self.assertContains(response,reverse(destination))
            self.assertContains(response,'mascot-guide-link')
            self.assertContains(response,'welcome.js')
        self.assertFalse(StaffAuditEvent.objects.exists())
        self.assertEqual(self.client.post(reverse('welcome')).status_code,405)

    def test_home_links_newcomer_and_existing_login_guards(self):
        response=self.client.get(reverse('home'))
        self.assertContains(response,reverse('welcome'))
        self.assertEqual(self.client.get(reverse('campus:friends')).status_code,302)
        self.assertEqual(self.client.get(reverse('campus:errand_create')).status_code,302)
        self.assertEqual(self.client.get(reverse('campus:booking')).status_code,302)
