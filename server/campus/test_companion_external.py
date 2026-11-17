import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from . import companion_external as external
from .companion_chat import ModelUnavailable
from . import test_task_assistant as task_tests


class ExternalRoutingTests(SimpleTestCase):
    def test_saved_official_key_is_compatible_and_router_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'private_credentials'/'external_ai.json'
            path.parent.mkdir()
            with override_settings(BASE_DIR=Path(folder),COMPANION_EXTERNAL_API_KEY=''), patch.dict('os.environ',{'DEEPSEEK_API_KEY':''}):
                # Existing DS key was saved under the old field; no secret migration needed.
                path.write_text(json.dumps({'openrouter_api_key':'sk-official-test'}),encoding='utf-8')
                self.assertEqual(external.api_key(),'sk-official-test')
                path.write_text(json.dumps({'deepseek_api_key':'sk-official-new'}),encoding='utf-8')
                self.assertEqual(external.api_key(),'sk-official-new')
                path.write_text(json.dumps({'openrouter_api_key':'sk-or-v1-not-for-deepseek'}),encoding='utf-8')
                self.assertEqual(external.api_key(),'')

    @patch.object(external, 'cloud_answer')
    @patch.object(external, 'local_decision', return_value=True)
    @patch.object(external, 'configured', return_value=True)
    def test_no_consent_never_calls_models(self, configured, judge, cloud):
        self.assertIsNone(external.try_external('Explain sorting', [], 'en', False)[0])
        judge.assert_not_called();cloud.assert_not_called()

    @patch.object(external, 'cloud_answer')
    @patch.object(external, 'local_decision', return_value=True)
    @patch.object(external, 'configured', return_value=True)
    def test_private_and_campus_questions_stay_local(self, configured, judge, cloud):
        for question in ('我的学号123456789，帮我写邮件', 'my password is hello',
                         '我的病情需要诊断', 'мой паспорт 123456789',
                         '私の住所を翻訳して', '帮我预约自习室'):
            self.assertIsNone(external.try_external(question, [], 'zh', True)[0])
        judge.assert_not_called();cloud.assert_not_called()

    @patch.object(external, 'cloud_answer', return_value={'message': 'A public answer', 'model': 'free-model'})
    @patch.object(external, 'local_decision', return_value=True)
    @patch.object(external, 'configured', return_value=True)
    def test_local_model_routes_current_question_without_history(self, configured, judge, cloud):
        history=[{'role':'user','content':'LOCAL_HISTORY_ONLY'}]
        result, note=external.try_external('Compare sorting algorithms', history, 'en', True)
        self.assertEqual(result['model'], 'free-model')
        judge.assert_called_once_with('Compare sorting algorithms', history)
        cloud.assert_called_once_with('Compare sorting algorithms', 'en')

    @patch.object(external, 'cloud_answer')
    @patch.object(external, 'local_decision', side_effect=ModelUnavailable('format'))
    @patch.object(external, 'configured', return_value=True)
    def test_local_router_failure_does_not_delegate(self, configured, judge, cloud):
        self.assertIsNone(external.try_external('Explain sorting', [], 'en', True)[0])
        cloud.assert_not_called()

    @patch.object(external, 'cloud_answer', side_effect=ModelUnavailable('429'))
    @patch.object(external, 'local_decision', return_value=True)
    @patch.object(external, 'configured', return_value=True)
    def test_cloud_failure_falls_back(self, configured, judge, cloud):
        result, note=external.try_external('Explain sorting', [], 'en', True)
        self.assertIsNone(result);self.assertIn('回退', note)

    @patch.object(external, 'request_json')
    def test_judge_uses_constrained_local_generation(self, request):
        request.return_value={'response':'{"route":"external","reason":"complex"}'}
        self.assertTrue(external.local_decision('Explain algorithms', []))
        self.assertEqual(request.call_args.args[0], '/api/generate')
        request.return_value={'response':'{"route":"external","reason":"private"}'}
        self.assertFalse(external.local_decision('anything', []))
        request.return_value={'response':'{"route":"execute","reason":"complex"}'}
        with self.assertRaises(ModelUnavailable):external.local_decision('anything', [])

    @patch.object(external, 'api_key', return_value='TEST_KEY_MUST_STAY_SERVER_SIDE')
    @patch.object(external, 'build_opener')
    def test_provider_payload_is_official_direct_and_minimal(self, opener, key):
        response=MagicMock();response.read.return_value=json.dumps({'model':'deepseek-flash','choices':[{'message':{'content':'Answer'}}]}).encode()
        opener.return_value.open.return_value.__enter__.return_value=response
        self.assertEqual(external.cloud_answer('PUBLIC_QUESTION', 'en')['message'],'Answer')
        req=opener.return_value.open.call_args.args[0];body=json.loads(req.data)
        self.assertEqual(req.full_url,external.ENDPOINT)
        self.assertEqual(body['model'],'deepseek-flash')
        self.assertEqual(req.full_url,'https://api.deepseek.com/chat/completions')
        self.assertEqual(body['thinking'],{'type':'disabled'})
        self.assertEqual(body['max_tokens'],800)
        self.assertNotIn('models',body)
        self.assertNotIn('provider',body)
        self.assertEqual([m['role'] for m in body['messages']],['system','user'])
        self.assertNotIn('tools',body)
        self.assertNotIn('TEST_KEY',str(body))

    @patch.object(external, 'api_key', return_value='TEST_KEY')
    @patch.object(external, 'build_opener')
    def test_other_brand_is_not_labeled_as_deepseek(self, opener, key):
        response=MagicMock()
        response.read.return_value=json.dumps({'model':'another-brand/model:free',
            'choices':[{'message':{'content':'Answer'}}]}).encode()
        opener.return_value.open.return_value.__enter__.return_value=response
        with self.assertRaises(ModelUnavailable):external.cloud_answer('Public question', 'en')


class HybridEndpointTests(TestCase):
    setUp=task_tests.TaskAssistantTests.setUp
    post=task_tests.TaskAssistantTests.post

    @patch('campus.task_assistant.answer')
    @patch.object(external, 'try_external', return_value=({'message':'Cloud answer','model':'test:free'},'External route'))
    def test_cloud_answer_has_source_and_never_executes_actions(self, route, local):
        response=self.post('chat',{'message':'Compare complex algorithms','external_allowed':True}).json()
        self.assertEqual(response['mode'],'external_ai');self.assertNotIn('actions',response)
        local.assert_not_called()
        from .models import VenueBooking
        self.assertFalse(VenueBooking.objects.exists())

    @patch('campus.task_assistant.answer',return_value='Local answer')
    @patch.object(external, 'try_external', return_value=(None,'Fallback'))
    def test_fallback_is_labeled(self, route, local):
        response=self.post('chat',{'message':'Explain recursion','external_allowed':True}).json()
        self.assertEqual(response['mode'],'local_ai');self.assertEqual(response['route_note'],'Fallback')

    def test_invalid_consent_type_is_rejected(self):
        self.assertEqual(self.post('chat',{'message':'hello','external_allowed':'yes'}).status_code,400)

    @patch.object(external, 'configured',return_value=False)
    def test_unconfigured_switch_is_disabled(self, configured):
        response=self.client.get(reverse('task-assistant'))
        self.assertContains(response,'id="assistant-external" disabled')
