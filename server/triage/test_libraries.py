import json
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from .models import DoctorProfile,Department
from .knowledge import load_knowledge,retrieve
from .drug_library import load_drugs,retrieve_drug_candidates
from .management.commands.import_drug_labels import normalized,GENERIC_VARIANTS


class LibraryTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('library_doctor',password='Mint-Sturdy!73')
        DoctorProfile.objects.create(user=self.user,department=Department.objects.get(slug='bone'),display_name='资料测试医生')
        self.client.force_login(self.user)

    def test_chinese_disease_retrieval_and_ordinary_symptom_never_selects_genetic_condition(self):
        names={item['title'] for item in retrieve('head','高血压伴头痛')}
        self.assertIn('High Blood Pressure',names);self.assertIn('Headache',names)
        self.assertTrue(all(item.get('kind')!='genetic_condition' for item in retrieve('head','普通头痛')))
        self.assertTrue(any(item['title'].lower()=='marfan syndrome' for item in retrieve('chest','已诊断马凡综合征')))
        self.assertTrue(any(item['title']=='Diabetes Type 2' for item in retrieve('head','2型糖尿病')))

    def test_drug_import_has_real_sources_and_single_ingredient_matching_is_strict(self):
        data=load_drugs()
        self.assertGreater(len(data['records']),150)
        for item in data['records']:
            allowed={normalized(value) for value in [item['english'],*GENERIC_VARIANTS.get(item['english'],[])]}
            self.assertTrue(all(normalized(name) in allowed for name in item['generic_names']))
            self.assertTrue(item['source_url'].startswith('https://dailymed.nlm.nih.gov/dailymed/'))
            self.assertTrue(item['excerpts'].get('indications_and_usage') or item['excerpts'].get('purpose'))
        self.assertNotEqual(normalized('AMOXICILLIN AND CLAVULANATE POTASSIUM'),normalized('amoxicillin'))

    def test_doctor_library_chinese_search_detail_and_patient_cannot_access(self):
        response=self.client.get(reverse('doctor-drugs'),{'q':'阿莫西林'})
        self.assertContains(response,'阿莫西林')
        item=next(item for item in load_drugs()['records'] if item['name']=='阿莫西林')
        self.assertContains(self.client.get(reverse('doctor-drug-detail',args=[item['id']])),'适应证（英文节选）')
        patient=User.objects.create_user('library_patient',password='Mint-Sturdy!73');self.client.force_login(patient)
        for url in (reverse('doctor-drugs'),reverse('doctor-drug-detail',args=[item['id']]),reverse('doctor-knowledge')):
            self.assertEqual(self.client.get(url).status_code,403)

    def test_knowledge_library_search_and_pagination_do_not_mix_patient_records(self):
        response=self.client.get(reverse('doctor-knowledge'),{'q':'马凡','kind':'genetics'})
        self.assertContains(response,'Marfan syndrome')
        self.assertContains(self.client.get(reverse('doctor-knowledge'),{'q':'高血压'}),'High Blood Pressure')
        self.assertLessEqual(len(self.client.get(reverse('doctor-knowledge')).context['page']),20)

    def test_auto_drug_retrieval_reads_indications_and_leaves_boxed_or_nonoral_for_explicit_selection(self):
        candidates=retrieve_drug_candidates('医生已诊断高血压')
        self.assertTrue(candidates)
        self.assertTrue(all('hypertension' in item['indications'].lower() for item in candidates.values()))
        self.assertTrue(all(not item['boxed_warning'] and item['routes']==['ORAL'] for item in candidates.values()))
        warfarin=next(item for item in load_drugs()['records'] if item['name']=='华法林')
        selected=retrieve_drug_candidates('医生核对药品原文',warfarin['id'])
        self.assertIn(warfarin['id'],selected)
        self.assertEqual(retrieve_drug_candidates('尚未确定疾病'),{})
