import json
import uuid
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase,Client
from django.urls import reverse
from accounts.models import Profile
from .models import Consultation,Department,DoctorProfile,CaseConference
from .medication import medication_reference
from .ollama_client import ModelUnavailable


class MedicationTests(TestCase):
    def setUp(self):
        self.patient=User.objects.create_user('med_patient',password='Mint-Sturdy!73')
        self.profile=Profile.objects.create(user=self.patient,full_name='用药测试用户',gender='female',age=28)
        self.doctor=DoctorProfile.objects.create(user=User.objects.create_user('med_doctor',password='Mint-Sturdy!73'),department=Department.objects.get(slug='bone'),display_name='测试医生')
        self.other=DoctorProfile.objects.create(user=User.objects.create_user('other_med_doctor',password='Mint-Sturdy!73'),department=Department.objects.get(slug='neuro'),display_name='其他科室医生')
        self.record=Consultation.objects.create(user=self.patient,request_key=uuid.uuid4(),department=self.doctor.department,part='left_leg',description='功能测试：左膝盖疼痛',feeling='mild',level='low',followup_answers={'history':'没有已知既往病史'})
        self.information={'assessment':'已评估轻度关节疼痛，需进一步核对对症药物。','allergies':'无已知药物过敏','current_medicines':'没有正在用药','risks':'未发现相关用药风险','confirmed':True}

    @patch('triage.medication.request_json',return_value={'message':{'content':'{"choices":["acetaminophen"]}'}})
    def test_whitelisted_reference_has_fixed_sources_and_no_dose_or_identity(self,mock):
        result=medication_reference(self.record,self.information)
        self.assertEqual(result['engine'],'ollama');self.assertEqual(result['candidates'][0]['name'],'对乙酰氨基酚')
        self.assertTrue(result['candidates'][0]['url'].startswith('https://dailymed.nlm.nih.gov/'))
        content=mock.call_args.args[1]['messages'][1]['content']
        self.assertNotIn(self.profile.full_name,content);self.assertNotIn(self.patient.username,content)
        self.assertNotIn('mg',json.dumps(result));self.assertNotIn('dosage',json.dumps(result))

    @patch('triage.medication.request_json')
    def test_unknown_information_age_and_emergency_skip_model(self,mock):
        for field in ('allergies','current_medicines','risks'):
            result=medication_reference(self.record,{**self.information,field:'不清楚'})
            self.assertEqual(result['candidates'],[])
        self.assertEqual(medication_reference(self.record,{**self.information,'confirmed':False})['candidates'],[])
        for age in (None,10,70):
            self.profile.age=age;self.profile.save();self.patient.refresh_from_db();self.record.user=self.patient
            self.assertEqual(medication_reference(self.record,self.information)['candidates'],[])
        self.profile.age=28;self.profile.save();self.patient.refresh_from_db();self.record.user=self.patient;self.record.emergency=True
        self.assertEqual(medication_reference(self.record,self.information)['candidates'],[]);mock.assert_not_called()

    @patch('triage.medication.request_json',return_value={'message':{'content':'{"choices":["ibuprofen"]}'}})
    def test_allergy_prior_medicines_and_risks_remove_candidate_before_model(self,mock):
        result=medication_reference(self.record,{**self.information,'allergies':'对布洛芬过敏'})
        self.assertEqual(result['candidates'],[])
        context=json.loads(mock.call_args.args[1]['messages'][1]['content'])
        self.assertNotIn('ibuprofen',[item['id'] for item in context['candidate_references']])
        self.record.followup_answers={'history':'高血压，既往对布洛芬过敏'}
        result=medication_reference(self.record,self.information)
        self.assertEqual(result['candidates'],[])
        self.assertEqual(medication_reference(self.record,{**self.information,'current_medicines':'正在用对乙酰氨基酚和布洛芬'})['candidates'],[])

    @patch('triage.medication.request_json')
    def test_pregnancy_or_uncovered_assessment_does_not_invent_drug(self,mock):
        for change in ({'risks':'正在妊娠'},{'assessment':'诊断尚未确认，疑似肺部感染'}):
            self.assertEqual(medication_reference(self.record,{**self.information,**change})['candidates'],[])
        mock.assert_not_called()

    @patch('triage.medication.request_json')
    def test_invalid_or_combination_output_and_model_failure_never_expose_suggestion(self,mock):
        for value in ('{"choices":["unknown"]}','{"choices":["acetaminophen","ibuprofen"]}','{"choices":[{"name":"a"}]}','[]'):
            mock.return_value={'message':{'content':value}}
            self.assertEqual(medication_reference(self.record,self.information)['candidates'],[])
        mock.side_effect=ModelUnavailable('模型未启动')
        self.assertEqual(medication_reference(self.record,self.information)['engine'],'unavailable')

    @patch('triage.doctor_views.medication_reference')
    def test_doctor_only_scoped_post_and_patient_api_excludes_reference(self,mock):
        mock.return_value={'engine':'ollama','candidates':[{'name':'医生内部用药测试标记'}]}
        endpoint=reverse('doctor-medication',args=[self.record.pk])
        self.client.force_login(self.patient)
        self.assertEqual(self.client.post(endpoint,self.information).status_code,403)
        self.client.force_login(self.other.user)
        self.assertEqual(self.client.post(endpoint,self.information).status_code,404)
        self.client.force_login(self.doctor.user)
        self.assertEqual(self.client.post(endpoint,{}).status_code,302);mock.assert_not_called()
        self.assertEqual(self.client.post(endpoint,self.information).status_code,302)
        self.record.refresh_from_db();self.assertEqual(self.record.doctor_medication_reference['engine'],'ollama')
        self.assertEqual(self.record.doctor_reply,'')
        self.assertContains(self.client.get(reverse('doctor-case',args=[self.record.pk])),'医生内部用药测试标记')
        self.client.force_login(self.patient)
        data=self.client.get(reverse('inbox')).json()
        self.assertNotIn('医生内部用药测试标记',json.dumps(data,ensure_ascii=False))
        client=Client(enforce_csrf_checks=True);client.force_login(self.doctor.user)
        self.assertEqual(client.post(endpoint,self.information).status_code,403)

    @patch('triage.doctor_views.medication_reference')
    def test_revoked_conference_during_model_generation_cannot_save_reference(self,mock):
        invitation=CaseConference.objects.create(consultation=self.record,requested_by=self.doctor,target_department=self.other.department,accepted_by=self.other,status='accepted',reason='测试')
        def revoke(*args):
            invitation.status='revoked';invitation.save(update_fields=['status'])
            return {'engine':'ollama','candidates':[]}
        mock.side_effect=revoke;self.client.force_login(self.other.user)
        self.assertEqual(self.client.post(reverse('doctor-medication',args=[self.record.pk]),self.information).status_code,403)
        self.record.refresh_from_db();self.assertEqual(self.record.doctor_medication_reference,{})
