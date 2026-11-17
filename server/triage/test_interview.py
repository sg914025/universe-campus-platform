import json
import uuid
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from accounts.models import Profile
from .models import Consultation
from .interview import interview_step
from .knowledge import retrieve
from .ollama_client import ModelUnavailable
from .parts import assess_description


class InterviewTests(TestCase):
    def setUp(self):
        user=User.objects.create_user('interview_patient',password='Mint-Sturdy!73')
        Profile.objects.create(user=user,full_name='测试用户',gender='female')
        self.client.force_login(user)
        self.payload={'accepted_notice':True,'part':'left_leg','detail':'膝盖','description':'左膝盖隐痛',
                      'duration':'','feeling':'mild','answers':{}}

    def post(self,**changes):
        return self.client.post(reverse('advanced-followup'),json.dumps({**self.payload,**changes}),content_type='application/json')

    @patch('triage.interview.choose_question',side_effect=ModelUnavailable('模型未启动'))
    def test_fallback_is_visible_and_followup_does_not_create_record(self,mock):
        data=self.post().json()
        self.assertEqual(data['engine'],'fallback')
        self.assertEqual(data['question']['key'],'location')
        self.assertEqual(Consultation.objects.count(),0)

    @patch('triage.interview.choose_question',return_value='location')
    def test_actual_model_choice_retains_source_links_and_known_coordinates(self,mock):
        data=self.post().json()
        self.assertEqual(data['engine'],'ollama')
        self.assertTrue(any('Knee' in source['title'] for source in data['sources']))
        self.assertTrue(all(source['url'].startswith('https://medlineplus.gov/') for source in data['sources']))

    @patch('triage.interview.choose_question',side_effect=lambda choices,*args: choices[0]['id'])
    def test_side_detail_location_steps_and_unclear_side_not_guessed(self,mock):
        data=self.post(part='legs',detail='').json()
        self.assertEqual(data['question']['key'],'side')
        data=self.post(part='legs',detail='',answers={'side':'说不清'}).json()
        self.assertEqual(data['part'],'legs')
        self.assertIsNone(data['focus'])
        data=self.post(part='legs',detail='',answers={'side':'左侧','detail':'膝盖','location':'膝盖内侧'}).json()
        self.assertEqual(data['part'],'left_leg')
        self.assertEqual(data['detail'],'膝盖')
        self.assertEqual(data['focus']['label'],'膝盖内侧')
        self.assertEqual(data['question']['key'],'sensation')

    @patch('triage.interview.choose_question')
    def test_emergency_in_any_answer_interrupts_before_model(self,mock):
        data=self.post(answers={'associated':'呼吸困难'}).json()
        self.assertEqual(data['phase'],'urgent')
        mock.assert_not_called()
        self.assertIn('不要等待',data['message'])

    @patch('triage.interview.choose_question')
    def test_complete_answers_produce_review_and_do_not_save(self,mock):
        answers={'location':'膝盖内侧','sensation':'隐痛','duration':'两天','severity':'还能正常活动',
                 'associated':'没有明显其他表现','trigger':'活动时更明显','history':'没有已知既往病史'}
        data=self.post(answers=answers).json()
        self.assertEqual(data['phase'],'review')
        self.assertEqual(Consultation.objects.count(),0)
        mock.assert_not_called()

    def test_invalid_answers_notice_and_auth_are_rejected(self):
        for changes in [{'answers':[]},{'answers':{'unknown':'a'}},{'answers':{'location':2}},
                        {'answers':{'location':'a'*201}},{'accepted_notice':False},{'part':'invalid'}]:
            self.assertEqual(self.post(**changes).status_code,400)
        self.client.logout()
        self.assertEqual(self.post().status_code,401)

    def test_negated_emergency_words_do_not_claim_emergency(self):
        self.assertFalse(assess_description('膝盖疼，没有呼吸困难，无胸痛','mild')[1])
        self.assertTrue(assess_description('没有胸痛，但呼吸困难','mild')[1])

    @patch('triage.interview.choose_question',side_effect=lambda choices,*args: choices[0]['id'])
    def test_free_text_locates_only_unambiguous_position_and_keeps_red_flags(self,mock):
        data=self.post(answers={'location':'膝盖里面隐隐疼'}).json()
        self.assertEqual(data['focus']['label'],'膝盖内侧')
        data=self.post(answers={'location':'不是内侧，位置说不清'}).json()
        self.assertIsNone(data['focus'])
        data=self.post(answers={'location':'膝盖里面疼，同时呼吸困难'}).json()
        self.assertEqual(data['phase'],'urgent')

    @patch('triage.views.create_report')
    def test_confirmed_followup_record_is_saved_for_doctor_with_idempotent_key(self,mock):
        from .test_doctors import report
        mock.return_value=report()
        payload={**self.payload,'request_key':str(uuid.uuid4()),'answers':{'location':'膝盖内侧','severity':'很明显，想请医生确认'}}
        results=[self.client.post(reverse('advanced-assess'),json.dumps(payload),content_type='application/json') for _ in range(2)]
        self.assertTrue(results[0].json()['queued'])
        self.assertEqual(results[0].json()['code'],results[1].json()['code'])
        record=Consultation.objects.get()
        self.assertEqual(record.followup_answers['location'],'膝盖内侧')
        self.assertEqual(record.feeling,'severe')

    @patch('triage.interview.choose_question',side_effect=lambda choices,*args: choices[0]['id'])
    def test_history_is_asked_before_review_and_raw_answer_is_retained(self,mock):
        answers={'location':'膝盖内侧','sensation':'隐痛','duration':'两天','severity':'还能正常活动',
                 'associated':'没有明显其他表现','trigger':'活动时更明显'}
        data=self.post(answers=answers).json()
        self.assertEqual(data['question']['key'],'history')
        answers['history']='高血压，医生开了长期用药'
        data=self.post(answers=answers).json()
        self.assertEqual(data['phase'],'review')
        self.assertIn({'label':'既往病史','value':answers['history']},data['summary'])
