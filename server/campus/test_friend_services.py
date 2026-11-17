import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase,Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import Profile
from 帖子.models import follow,profile,post,chat_message
from .models import FriendPreference,FriendMoment,SharedBooking,Venue,VenueBooking


class FriendServicesTests(TestCase):
    def setUp(self):
        self.users=[]
        for name in ('friend_owner','friend_receiver','friend_stranger'):
            user=get_user_model().objects.create_user(name,password='test-only')
            Profile.objects.create(user=user,full_name=name,gender='other')
            profile.objects.create(user=user)
            self.users.append(user)
        self.owner,self.receiver,self.stranger=self.users
        follow.objects.create(user=self.owner,target=self.receiver)
        follow.objects.create(user=self.receiver,target=self.owner)
        self.client.force_login(self.owner)
        self.url=reverse('campus:friend-hub')
        venue=Venue.objects.create(kind='study',building='A',name='测试座位')
        self.booking=VenueBooking.objects.create(user=self.owner,venue=venue,day=timezone.localdate()+timedelta(days=1),slot='14',request_key=uuid.uuid4())

    def test_home_roster_only_friends(self):
        self.assertContains(self.client.get('/'),'home-friends')
        data=self.client.get(reverse('campus:friend-roster')).json()
        self.assertEqual([x['name'] for x in data['friends']],[self.receiver.username])

    def test_moments_friends_only_and_retract(self):
        self.client.post(self.url,{'action':'moment','content':'私密日常测试'})
        item=FriendMoment.objects.get(author=self.owner)
        self.client.force_login(self.receiver)
        self.assertContains(self.client.get(self.url),'私密日常测试')
        self.client.force_login(self.stranger)
        self.assertNotContains(self.client.get(self.url),'私密日常测试')
        self.assertEqual(self.client.post(self.url,{'action':'delete','moment':item.pk}).status_code,404)
        self.client.force_login(self.owner)
        self.client.post(self.url,{'action':'delete','moment':item.pk})
        item.refresh_from_db();self.assertTrue(item.is_hidden)

    def test_share_card_requires_owner_and_mutual_friend(self):
        payload={'action':'share','share_kind':'booking','friend':self.receiver.pk,'resource':self.booking.pk}
        self.assertEqual(self.client.post(self.url,payload).status_code,302)
        share=SharedBooking.objects.get()
        url=reverse('campus:friend-shared-card',args=[share.pk])
        self.client.force_login(self.receiver)
        self.assertContains(self.client.get(url),'测试座位')
        self.assertEqual(self.client.post(self.url,dict(payload,friend=self.owner.pk)).status_code,404)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(url).status_code,403)
        follow.objects.filter(user=self.owner,target=self.receiver).delete()
        self.client.force_login(self.receiver)
        self.assertEqual(self.client.get(url).status_code,403)

    def test_share_only_own_post(self):
        item=post.objects.create(author=self.stranger,title='other',content='other')
        self.assertEqual(self.client.post(self.url,{'action':'share','share_kind':'post','friend':self.receiver.pk,'resource':item.pk}).status_code,404)
        item.author=self.owner;item.save()
        self.assertEqual(self.client.post(self.url,{'action':'share','share_kind':'post','friend':self.receiver.pk,'resource':item.pk}).status_code,302)
        self.assertEqual(chat_message.objects.get().shared_post_id,item.pk)

    def test_translation_receiver_only_original_preserved_and_auto_country(self):
        FriendPreference.objects.create(user=self.owner,country='CN',language='zh')
        FriendPreference.objects.create(user=self.receiver,country='RU',language='ru')
        row=chat_message.objects.create(sender=self.owner,receiver=self.receiver,content='明天一起去图书馆吗？')
        url=reverse('campus:friend-message-translation',args=[row.pk])
        self.assertEqual(self.client.post(url).status_code,404)
        self.client.force_login(self.stranger);self.assertEqual(self.client.post(url).status_code,404)
        self.client.force_login(self.receiver)
        page=self.client.get(reverse('campus:chat',args=[self.owner.pk]))
        self.assertContains(page,'data-auto-translate="yes"')
        with patch('campus.friend_services.local_translation',return_value='Пойдём завтра в библиотеку?') as translate:
            self.assertEqual(self.client.post(url).json()['language'],'ru')
            translate.assert_called_once_with(row.content,'ru')
        row.refresh_from_db();self.assertEqual(row.content,'明天一起去图书馆吗？')
        row.is_hidden=True;row.save();self.assertEqual(self.client.post(url).status_code,404)

    def test_csrf_and_invalid_preference(self):
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.owner)
        self.assertEqual(strict.post(self.url,{'action':'moment','content':'x'}).status_code,403)
        self.client.post(self.url,{'action':'preferences','country':'invalid','language':'ru'})
        self.assertFalse(FriendPreference.objects.filter(user=self.owner).exists())

    def test_translation_number_protection_and_local_failure(self):
        from django.core.cache import cache
        from .friend_services import local_translation
        from triage.ollama_client import ModelUnavailable
        cache.clear()
        with patch('campus.friend_services.request_json',return_value={'response':'{"translation":"Завтра в UVNUM0TOKEN:UVNUM1TOKEN"}'}):
            self.assertEqual(local_translation('明天14:00','ru'),'Завтра в 14:00')
        with patch('campus.friend_services.request_json',return_value={'response':'{"translation":"завтра"}'}):
            with self.assertRaises(ModelUnavailable):local_translation('明天15:00','ru')
        row=chat_message.objects.create(sender=self.receiver,receiver=self.owner,content='测试离线')
        with patch('campus.friend_services.local_translation',side_effect=ModelUnavailable()):
            self.assertEqual(self.client.post(reverse('campus:friend-message-translation',args=[row.pk])).status_code,503)
        row.refresh_from_db();self.assertEqual(row.content,'测试离线')
