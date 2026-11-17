import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import Profile
from 帖子.models import chat_message, follow, post
from 跑腿.models import task, question
from triage.models import Consultation, Department, RoomAppointment
from .models import Venue, VenueBooking
from .services import personal_services, unread_count


class ServiceHubTests(TestCase):
    def setUp(self):
        users=get_user_model()
        self.me=users.objects.create_user('service-owner')
        self.friend=users.objects.create_user('service-friend')
        self.other=users.objects.create_user('service-other')
        for user in (self.me,self.friend,self.other):
            Profile.objects.create(user=user,full_name='测试用户',gender='other')
        follow.objects.create(user=self.me,target=self.friend)
        follow.objects.create(user=self.friend,target=self.me)
        self.chat=chat_message.objects.create(sender=self.friend,receiver=self.me,content='PRIVATE CHAT')
        self.hidden=chat_message.objects.create(sender=self.friend,receiver=self.me,content='HIDDEN CHAT',is_hidden=True)
        self.stranger=chat_message.objects.create(sender=self.other,receiver=self.me,content='STRANGER CHAT')
        self.foreign=chat_message.objects.create(sender=self.friend,receiver=self.other,content='FOREIGN CHAT')
        self.department=Department.objects.first() or Department.objects.create(slug='test',name='测试科室')
        self.case=Consultation.objects.create(user=self.me,request_key=uuid.uuid4(),part='head',description='PRIVATE SYMPTOM',feeling='mild',level='low',department=self.department,status='replied',doctor_reply='PRIVATE REPLY',replied_at=timezone.now())
        self.question=question.objects.create(user=self.me,content='PRIVATE QUESTION',reply_unread=True)
        self.order=task.objects.create(owner=self.me,runner=self.friend,title='MY ORDER',description='PRIVATE ORDER',address='PRIVATE ADDRESS',phone='PRIVATE PHONE',price='2.00',status='delivered')
        self.foreign_order=task.objects.create(owner=self.other,title='FOREIGN ORDER',description='other',address='other',phone='other',price='2.00')
        self.client.force_login(self.me)

    def test_counts_and_owner_filtered_records(self):
        data=personal_services(self.me)
        self.assertEqual(data['unread_total'],3)
        self.assertEqual({row['kind'] for row in data['notices']},{'forum','health','errands'})
        self.assertEqual(data['active_errands'],1)
        self.assertEqual(data['awaiting_confirmation'],1)
        self.assertEqual(list(data['errands']),[self.order])
        self.assertNotIn(self.foreign_order,list(data['errands']))

    def test_get_does_not_mark_read_or_expose_message_bodies(self):
        response=self.client.get(reverse('my-services'))
        self.assertEqual(response.status_code,200)
        for private in ('PRIVATE CHAT','HIDDEN CHAT','STRANGER CHAT','FOREIGN CHAT','PRIVATE SYMPTOM','PRIVATE REPLY','PRIVATE QUESTION','PRIVATE ADDRESS','PRIVATE PHONE','FOREIGN ORDER'):
            self.assertNotContains(response,private)
        self.chat.refresh_from_db();self.assertFalse(self.chat.is_read)
        self.case.refresh_from_db();self.assertFalse(self.case.reply_read)
        self.assertIn('no-store',response.headers['Cache-Control'])

    def test_read_reuses_module_states_and_preserves_actions(self):
        for kind,row,field,expected in [('forum',self.chat,'is_read',True),('health',self.case,'reply_read',True),('errands',self.question,'reply_unread',False)]:
            response=self.client.post(reverse('service-notice-read'),{'kind':kind,'id':row.pk})
            self.assertRedirects(response,reverse('my-services'))
            row.refresh_from_db();self.assertEqual(getattr(row,field),expected)
        self.assertEqual(unread_count(self.me),0)
        self.order.refresh_from_db();self.assertEqual(self.order.status,'delivered')
        self.case.refresh_from_db();self.assertEqual(self.case.doctor_reply,'PRIVATE REPLY')

    def test_read_cannot_change_other_hidden_or_nonfriend_messages(self):
        for row in (self.hidden,self.stranger,self.foreign):
            response=self.client.post(reverse('service-notice-read'),{'kind':'forum','id':row.pk})
            self.assertEqual(response.status_code,404)
            row.refresh_from_db();self.assertFalse(row.is_read)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('service-notice-read'),{'kind':'health','id':self.case.pk}).status_code,404)
        self.assertEqual(self.client.post(reverse('service-notice-read'),{'kind':'errands','id':self.question.pk}).status_code,404)

    def test_login_methods_csrf_and_bad_ids(self):
        anonymous=Client()
        self.assertEqual(anonymous.get(reverse('my-services')).status_code,302)
        self.assertEqual(anonymous.get(reverse('service-unread')).status_code,302)
        self.assertEqual(self.client.get(reverse('service-notice-read')).status_code,405)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.me)
        self.assertEqual(csrf.post(reverse('service-notice-read'),{'kind':'forum','id':self.chat.pk}).status_code,403)
        for payload in ({'kind':'unknown','id':'1'},{'kind':'forum','id':'-1'},{'kind':'forum','id':'1'*100}):
            self.assertEqual(self.client.post(reverse('service-notice-read'),payload).status_code,400)

    def test_future_current_expired_and_cancelled_bookings(self):
        now=timezone.now();tomorrow=timezone.localdate()+timedelta(days=1)
        venue=Venue.objects.create(name='MY VENUE',kind='study')
        VenueBooking.objects.create(venue=venue,user=self.me,day=tomorrow,slot='08',request_key=uuid.uuid4())
        VenueBooking.objects.create(venue=venue,user=self.me,day=tomorrow,slot='10',request_key=uuid.uuid4(),status='cancelled')
        VenueBooking.objects.create(venue=venue,user=self.me,day=tomorrow-timedelta(days=2),slot='08',request_key=uuid.uuid4())
        for start,end,status in [(now-timedelta(minutes=5),now+timedelta(minutes=55),'confirmed'),(now-timedelta(hours=2),now-timedelta(hours=1),'confirmed'),(now+timedelta(hours=2),now+timedelta(hours=3),'cancelled')]:
            RoomAppointment.objects.create(user=self.me,room='room1',starts_at=start,ends_at=end,number=1,request_key=uuid.uuid4(),status=status)
        data=personal_services(self.me)
        self.assertEqual(data['upcoming_count'],2)
        self.assertEqual(len(data['bookings']),1)
        self.assertEqual(len(data['appointments']),1)
        self.assertEqual(data['appointments'][0].room_label,'诊室1')

    def test_four_language_templates_and_home_entry(self):
        for lang,heading in [('zh','我的服务'),('en','My services'),('ru','Мои сервисы'),('ja','マイサービス')]:
            self.client.cookies['campus_language']=lang
            response=self.client.get(reverse('my-services'))
            self.assertContains(response,heading)
            self.assertContains(response,'MY ORDER')
            self.assertContains(response,reverse('service-notice-read'))
            home=self.client.get(reverse('home'))
            self.assertContains(home,reverse('my-services'))
        self.assertEqual(self.client.get(reverse('service-unread')).json(),{'unread':3})

    def test_notification_limit_does_not_drop_total(self):
        chat_message.objects.bulk_create([chat_message(sender=self.friend,receiver=self.me,content='Test') for _ in range(25)])
        data=personal_services(self.me)
        self.assertEqual(data['unread_total'],28)
        self.assertEqual(len(data['notices']),20)
