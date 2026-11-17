import copy
import json
import re
import uuid
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from accounts.models import Profile
from .models import Consultation
from .report_translation import display_fields,remember_preview
from .ollama_client import ModelUnavailable


class ReportTranslationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=User.objects.create_user('report_owner')
        Profile.objects.create(user=self.user,full_name='界面测试',gender='other')
        self.client.force_login(self.user)
        self.report={'summary':'左手胀痛10天，需医生核实。','routing_reason':'手部不适，建议骨科检查。',
            'possible_causes':[{'name':'可能腱鞘炎','reason':'活动不适，不能确定病因。'}],
            'notice':'AI初步推测不等于确诊。','doctor_notes':'医生内部备注示例',
            'sources':[{'title':'Reference','url':'https://example.com/reference'}]}
        self.record=Consultation.objects.create(user=self.user,request_key=uuid.uuid4(),part='left_hand',
            detail='手指',description='原始描述保持不变',feeling='mild',level='low',ai_report=self.report)
        self.fields=display_fields(self.report)

    def translated_response(self,**changes):
        result={str(i):'Переведено '+ ' '.join(re.findall(r'\d+',text))+(' теносиновит' if '腱鞘炎' in text else '') for i,text in enumerate(self.fields.values())}
        result.update(changes)
        return {'response':json.dumps(result,ensure_ascii=False)}

    def send(self,**changes):
        return self.client.post('/api/report-translation/',json.dumps({'consultation_id':self.record.pk,'language':'ru',**changes}),content_type='application/json')

    @patch('triage.report_translation.request_json')
    def test_translates_own_report_and_keeps_source_private_fields_and_links(self,model):
        model.return_value=self.translated_response()
        result=self.send()
        self.assertEqual(result.status_code,200)
        report=result.json()['report'];self.assertIn('Переведено 10',report['summary'])
        self.assertEqual(report['sources'],self.report['sources'])
        self.assertEqual(report['doctor_notes'],self.report['doctor_notes'])
        prompt=model.call_args.args[1]['prompt']
        self.assertNotIn('医生内部备注示例',prompt)
        self.assertNotIn('原始描述保持不变',prompt)
        self.assertNotIn(self.user.username,prompt)
        self.record.refresh_from_db();self.assertEqual(self.record.ai_report,self.report)

    @patch('triage.report_translation.request_json')
    def test_cache_is_content_sensitive_and_does_not_reuse_other_source_links(self,model):
        model.return_value=self.translated_response();self.send();self.send()
        self.assertEqual(model.call_count,1)
        changed=copy.deepcopy(self.report);changed['sources'][0]['url']='https://example.com/other'
        self.record.ai_report=changed;self.record.save(update_fields=['ai_report'])
        response=self.send();self.assertEqual(model.call_count,2)
        self.assertEqual(response.json()['report']['sources'],changed['sources'])

    @patch('triage.report_translation.request_json')
    def test_owner_and_csrf_checks_happen_before_model_call(self,model):
        other=User.objects.create_user('other_report_owner');Profile.objects.create(user=other,full_name='另一测试用户',gender='other')
        self.client.force_login(other);self.assertEqual(self.send().status_code,404)
        self.client.logout();self.assertEqual(self.send().status_code,401)
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.user)
        self.assertEqual(secure.post('/api/report-translation/',{},content_type='application/json').status_code,403)
        model.assert_not_called()

    @patch('triage.report_translation.request_json')
    def test_preview_is_scoped_to_owner_and_expires(self,model):
        model.return_value=self.translated_response();key=uuid.uuid4();remember_preview(self.user.pk,key,self.report)
        payload={'request_key':str(key),'language':'ru'}
        response=self.client.post('/api/report-translation/',json.dumps(payload),content_type='application/json')
        self.assertEqual(response.status_code,200)
        cache.delete(f'report-source:{self.user.pk}:{key}')
        self.assertEqual(self.client.post('/api/report-translation/',json.dumps(payload),content_type='application/json').status_code,404)

    @patch('triage.report_translation.request_json')
    def test_failed_or_invalid_translation_never_claims_success(self,model):
        model.side_effect=ModelUnavailable('Unavailable')
        self.assertEqual(self.send().status_code,503)
        model.side_effect=None;model.return_value=self.translated_response(**{'0':'Перевод без числа'})
        self.assertEqual(self.send().status_code,503)
        model.return_value=self.translated_response(**{'0':'仍然是中文10'})
        self.assertEqual(self.send().status_code,503)
        self.record.refresh_from_db();self.assertEqual(self.record.ai_report,self.report)

    @patch('triage.report_translation.request_json')
    def test_chinese_and_invalid_requests_do_not_call_model(self,model):
        result=self.send(language='zh');self.assertEqual(result.status_code,200)
        self.assertFalse(result.json()['translated'])
        for extra in ({'language':'bad'},{'report':{'summary':'client text'}},{'consultation_id':True},{'request_key':str(uuid.uuid4())}):
            self.assertEqual(self.send(**extra).status_code,400)
        model.assert_not_called()
