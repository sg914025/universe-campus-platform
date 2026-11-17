import json
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.contrib.auth.models import User
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase,Client
from django.urls import reverse
from accounts.models import Profile
from .models import Department,DoctorProfile,Consultation,CaseConference,DiscussionMessage
from .reporting import create_report
from .ollama_client import ModelUnavailable


def report(**changes):
    data={'department':'bone','department_name':'骨科','engine':'ollama','summary':'左膝盖隐痛',
          'possible_causes':[{'name':'可能的软组织问题','reason':'活动时不适，需要医生检查核实。'}],
          'routing_reason':'关节部位不适建议骨科核实。','doctor_notes':'确认既往病史。','sources':[],
          'notice':'AI 推测不等于确诊。'}
    return {**data,**changes}


class DoctorWorkflowTests(TestCase):
    def setUp(self):
        self.bone=Department.objects.get(slug='bone');self.neuro=Department.objects.get(slug='neuro');self.digest=Department.objects.get(slug='digest')
        self.patient=User.objects.create_user('case_patient',password='Mint-Sturdy!73')
        Profile.objects.create(user=self.patient,full_name='本科室测试患者',gender='female',age=28)
        self.owner=self.make_doctor('bone_test',self.bone)
        self.guest=self.make_doctor('neuro_test',self.neuro)
        self.uninvited=self.make_doctor('digest_test',self.digest)
        self.neuro_other=self.make_doctor('neuro_second',self.neuro)
        self.case=Consultation.objects.create(user=self.patient,request_key=uuid.uuid4(),department=self.bone,part='left_leg',description='左膝盖疼',feeling='mild',level='low',ai_report=report(),followup_answers={'history':'医生曾诊断高血压，长期用药'})
        self.foreign=Consultation.objects.create(user=self.patient,request_key=uuid.uuid4(),department=self.digest,part='abdomen',description='其他科室专属描述',feeling='mild',level='low')

    def make_doctor(self,name,department):
        user=User.objects.create_user(name,password='Mint-Sturdy!73')
        return DoctorProfile.objects.create(user=user,department=department,display_name=name+'医生')

    def login(self,doctor):
        self.client.force_login(doctor.user)

    def test_role_login_and_patient_accounts_cannot_impersonate_doctors(self):
        response=self.client.post(reverse('doctor-login'),{'username':self.patient.username,'password':'Mint-Sturdy!73'})
        self.assertContains(response,'该账号没有所选后台的权限')
        self.assertNotIn('_auth_user_id',self.client.session)
        response=self.client.post(reverse('doctor-login'),{'username':self.owner.user.username,'password':'Mint-Sturdy!73'})
        self.assertRedirects(response,reverse('doctor-dashboard'))
        self.assertRedirects(self.client.get(reverse('guide')),reverse('doctor-dashboard'))
        self.client.logout()
        self.assertEqual(self.client.get(reverse('doctor-dashboard')).status_code,302)
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(reverse('doctor-dashboard')).status_code,403)

    def test_department_isolation_enforced_on_read_and_all_mutations(self):
        self.login(self.owner)
        self.assertContains(self.client.get(reverse('doctor-dashboard')),'左膝盖疼')
        self.assertNotContains(self.client.get(reverse('doctor-dashboard')),'其他科室专属描述')
        self.assertEqual(self.client.get(reverse('doctor-case',args=[self.foreign.pk])).status_code,404)
        for name in ('doctor-reply','doctor-discuss','doctor-invite'):
            self.assertEqual(self.client.post(reverse(name,args=[self.foreign.pk]),{'content':'越权测试','department':self.neuro.pk,'reason':'测试'}).status_code,404)
        self.assertEqual(DiscussionMessage.objects.count(),0)
        self.foreign.refresh_from_db();self.assertEqual(self.foreign.doctor_reply,'')

    def test_conference_accept_grants_one_case_to_one_doctor_and_revoke_removes_access(self):
        self.login(self.owner)
        self.client.post(reverse('doctor-invite',args=[self.case.pk]),{'department':self.neuro.pk,'reason':'请协助确认相关表现。'})
        invitation=CaseConference.objects.get()
        self.login(self.guest)
        dashboard=self.client.get(reverse('doctor-dashboard'))
        self.assertContains(dashboard,self.case.code)
        self.assertNotContains(dashboard,'本科室测试患者')
        self.assertNotContains(dashboard,'左膝盖疼')
        self.assertEqual(self.client.get(reverse('doctor-case',args=[self.case.pk])).status_code,404)
        self.client.post(reverse('doctor-invitation',args=[invitation.pk]),{'action':'accept'})
        self.assertContains(self.client.get(reverse('doctor-case',args=[self.case.pk])),'高血压')
        self.client.post(reverse('doctor-discuss',args=[self.case.pk]),{'content':'会诊内部讨论测试'})
        self.assertEqual(DiscussionMessage.objects.count(),1)
        self.assertEqual(self.client.get(reverse('doctor-case',args=[self.foreign.pk])).status_code,404)
        self.login(self.neuro_other)
        self.assertEqual(self.client.get(reverse('doctor-case',args=[self.case.pk])).status_code,404)
        self.login(self.uninvited)
        self.assertEqual(self.client.get(reverse('doctor-case',args=[self.case.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('doctor-invitation',args=[invitation.pk]),{'action':'accept'}).status_code,404)
        self.login(self.owner)
        self.assertContains(self.client.get(reverse('doctor-case',args=[self.case.pk])),'会诊内部讨论测试')
        self.client.post(reverse('doctor-revoke',args=[invitation.pk]))
        self.login(self.guest)
        self.assertEqual(self.client.get(reverse('doctor-case',args=[self.case.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('doctor-discuss',args=[self.case.pk]),{'content':'撤回后不能发言'}).status_code,404)

    def test_patient_receives_reply_and_report_but_never_internal_discussion(self):
        self.login(self.owner)
        self.client.post(reverse('doctor-discuss',args=[self.case.pk]),{'content':'绝不可公开的内部测试讨论'})
        self.client.post(reverse('doctor-reply',args=[self.case.pk]),{'content':'测试医生回复，请准备既往检查资料。'})
        self.client.force_login(self.patient)
        data=self.client.get(reverse('inbox')).json()
        item=next(x for x in data['messages'] if x['id']==self.case.pk)
        self.assertIn('测试医生回复',item['reply']);self.assertEqual(item['department'],'骨科')
        self.assertEqual(item['report']['engine'],'ollama');self.assertEqual(data['unread'],1)
        self.assertNotIn('绝不可公开',json.dumps(data,ensure_ascii=False))

    def test_invite_validation_decline_duplicate_and_csrf(self):
        self.login(self.owner)
        for values in [{'department':self.bone.pk,'reason':'本科室不需要邀请'}, {'department':self.neuro.pk,'reason':''}]:
            self.client.post(reverse('doctor-invite',args=[self.case.pk]),values)
        self.assertEqual(CaseConference.objects.count(),0)
        for _ in range(2):
            self.client.post(reverse('doctor-invite',args=[self.case.pk]),{'department':self.neuro.pk,'reason':'测试会诊'})
        self.assertEqual(CaseConference.objects.count(),1)
        invitation=CaseConference.objects.get();self.login(self.guest)
        self.client.post(reverse('doctor-invitation',args=[invitation.pk]),{'action':'decline'})
        self.assertEqual(self.client.get(reverse('doctor-case',args=[self.case.pk])).status_code,404)
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner.user)
        self.assertEqual(client.post(reverse('doctor-reply',args=[self.case.pk]),{'content':'测试'}).status_code,403)

    def test_admin_cannot_bypass_department_scope_with_staff_permission(self):
        from django.contrib.auth.models import Permission
        self.owner.user.is_staff=True;self.owner.user.save()
        self.owner.user.user_permissions.add(*Permission.objects.filter(codename__in=['view_consultation','change_consultation']))
        self.login(self.owner)
        self.assertNotContains(self.client.get(reverse('admin:triage_consultation_changelist')),self.foreign.code)
        self.client.post(reverse('admin:triage_consultation_change',args=[self.foreign.pk]),{'doctor_reply':'越权回复','_save':'保存'})
        self.foreign.refresh_from_db();self.assertEqual(self.foreign.doctor_reply,'')

    def test_seed_creates_non_staff_accounts_once_and_never_changes_existing_passwords(self):
        with TemporaryDirectory(dir=settings.BASE_DIR,prefix='test_doctors_') as directory:
            output=Path(directory)/'accounts.txt'
            call_command('create_demo_doctors',output=str(output),verbosity=0)
            self.assertTrue(output.exists())
            doctors=User.objects.filter(username__startswith='doctor_')
            self.assertEqual(doctors.count(),10);self.assertFalse(doctors.filter(is_staff=True).exists())
            hashes=list(doctors.order_by('username').values_list('password',flat=True))
            call_command('create_demo_doctors',output=str(output),verbosity=0)
            self.assertEqual(hashes,list(doctors.order_by('username').values_list('password',flat=True)))

    @patch('triage.views.create_report',return_value=report())
    def test_all_confirmed_cases_auto_route_with_history_and_idempotency(self,mock):
        self.client.force_login(self.patient)
        payload={'accepted_notice':True,'part':'left_leg','detail':'膝盖','description':'左膝盖疼','duration':'两天','feeling':'mild','answers':{'history':'高血压'},'request_key':str(uuid.uuid4())}
        data=self.client.post(reverse('advanced-assess'),json.dumps(payload),content_type='application/json').json()
        self.assertTrue(data['queued']);self.assertEqual(data['department'],'骨科')
        self.client.post(reverse('advanced-assess'),json.dumps(payload),content_type='application/json')
        mock.assert_called_once()
        record=Consultation.objects.get(request_key=payload['request_key'])
        self.assertEqual(record.followup_answers['history'],'高血压')
        self.assertEqual(record.ai_report['possible_causes'],report()['possible_causes'])


class ReportTests(TestCase):
    @patch('triage.reporting.request_json',return_value={'message':{'content':json.dumps(report(),ensure_ascii=False)}})
    def test_real_schema_result_and_no_identity_sent_to_model(self,mock):
        result=create_report('left_leg','膝盖','左膝盖疼','两天',{'history':'高血压'})
        self.assertEqual(result['engine'],'ollama');self.assertEqual(result['department'],'bone')
        request=mock.call_args.args[1]
        content=request['messages'][1]['content']
        self.assertIn('高血压',content);self.assertNotIn('password',content);self.assertNotIn('username',content)
        self.assertTrue(result['sources'])

    @patch('triage.reporting.request_json',side_effect=ModelUnavailable('AI 未启动'))
    def test_fallback_never_invents_causes(self,mock):
        result=create_report('head','头顶 / 太阳穴','头痛','三天',{})
        self.assertEqual(result['engine'],'fallback');self.assertEqual(result['department'],'neuro')
        self.assertEqual(result['possible_causes'],[])

    @patch('triage.reporting.request_json')
    def test_emergency_skips_model_and_routes_urgent(self,mock):
        result=create_report('chest','','胸痛并呼吸困难','刚出现',{},True)
        self.assertEqual(result['department'],'urgent');self.assertEqual(result['possible_causes'],[]);mock.assert_not_called()

    @patch('triage.reporting.request_json',return_value={'message':{'content':'{"department":"invalid"}'}})
    def test_malformed_model_output_cannot_select_unknown_department(self,mock):
        result=create_report('abdomen','上腹','腹痛','一天',{})
        self.assertEqual(result['engine'],'fallback');self.assertEqual(result['department'],'digest')
