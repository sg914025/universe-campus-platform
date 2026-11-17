import json
from unittest.mock import patch,MagicMock
from urllib.error import URLError
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import AIInvocation
from .ai_dashboard import asset_chart,usage_data
from triage.ollama_client import request_json,ModelUnavailable

class AIUsageTests(TestCase):
    def opener(self,raw):
        opener=MagicMock();opener.open.return_value.__enter__.return_value.read.return_value=json.dumps(raw).encode()
        return opener
    def test_local_inference_and_status_exclusion(self):
        with patch('triage.ollama_client.build_opener',return_value=self.opener({'response':'hello'})):
            request_json('/api/generate',{'model':'qwen3:4b','prompt':'private question'})
            request_json('/api/tags')
        row=AIInvocation.objects.get()
        self.assertEqual(row.provider,'ollama');self.assertTrue(row.success)
        self.assertNotIn('prompt',{f.name for f in row._meta.fields})
    def test_local_failure_counts_once(self):
        with patch('triage.ollama_client.build_opener') as opener:
            opener.return_value.open.side_effect=URLError('failure')
            with self.assertRaises(ModelUnavailable):request_json('/api/chat',{'model':'qwen3:4b'})
        self.assertFalse(AIInvocation.objects.get().success)
    def test_deepseek_success_failure_and_unconfigured(self):
        from .companion_external import cloud_answer
        with patch('campus.companion_external.api_key',return_value='test-only-not-a-real-key'),patch('campus.companion_external.build_opener',return_value=self.opener({'choices':[{'message':{'content':'hello'}}],'model':'deepseek-flash'})):
            self.assertEqual(cloud_answer('test','en')['message'],'hello')
        self.assertTrue(AIInvocation.objects.get().success)
        with patch('campus.companion_external.api_key',return_value='test-only-not-a-real-key'),patch('campus.companion_external.build_opener') as opener:
            opener.return_value.open.side_effect=URLError('failure')
            with self.assertRaises(ModelUnavailable):cloud_answer('test','en')
        self.assertEqual(AIInvocation.objects.filter(provider='deepseek',success=False).count(),1)
        with patch('campus.companion_external.api_key',return_value=''):
            with self.assertRaises(ModelUnavailable):cloud_answer('test','en')
        self.assertEqual(AIInvocation.objects.count(),2)
    def test_logging_failure_does_not_break_answer(self):
        from django.db import DatabaseError
        with patch('campus.ai_usage.logging.getLogger'),patch('campus.models.AIInvocation.objects.create',side_effect=DatabaseError('not ready')),patch('triage.ollama_client.build_opener',return_value=self.opener({'response':'fine'})):
            self.assertEqual(request_json('/api/generate',{'model':'qwen3:4b'})['response'],'fine')
    def test_aggregate_and_empty_assets(self):
        AIInvocation.objects.create(provider='ollama',model='qwen3:4b',success=True,duration_ms=100)
        AIInvocation.objects.create(provider='deepseek',model='deepseek-flash',success=False,duration_ms=200)
        data=usage_data();self.assertEqual((data['total'],data['success'],data['failed'],data['today']),(2,1,1,2))
        self.assertEqual(len(data['trend']),14)
        self.assertEqual(asset_chart([])['total'],0)
        assets=asset_chart([{'name':'账号','rows':30},{'name':'帖子','rows':10}])
        self.assertEqual(assets['total'],40);self.assertEqual(assets['rows'][1]['share'],25)
    def test_page_superadmin_only_no_raw_records(self):
        root=get_user_model().objects.create_user('usage_root',is_superuser=True,is_staff=True)
        user=get_user_model().objects.create_user('usage_user')
        url=reverse('security-ai')
        self.assertEqual(self.client.get(url).status_code,302)
        self.client.force_login(user);self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(root);response=self.client.get(url)
        self.assertEqual(response.status_code,200);self.assertContains(response,'AI 调用统计')
