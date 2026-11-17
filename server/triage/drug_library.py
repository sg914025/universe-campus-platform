import json
from functools import lru_cache
from pathlib import Path

DATA_FILE=Path(__file__).parent/'data'/'drug_labels.json'
FIELD_LABELS={'indications_and_usage':'适应证（英文节选）','purpose':'用途（英文节选）','contraindications':'禁忌（英文节选）',
              'boxed_warning':'重要警告（英文节选）','warnings':'警告（英文节选）','warnings_and_cautions':'警告与注意事项（英文节选）',
              'drug_interactions':'相互作用（英文节选）','pregnancy':'妊娠（英文节选）','pregnancy_or_breast_feeding':'妊娠及哺乳（英文节选）',
              'use_in_specific_populations':'特殊人群（英文节选）'}
ASSESSMENT_TERMS={
    '高血压':['hypertension'], '2型糖尿病':['type 2 diabetes'], '二型糖尿病':['type 2 diabetes'],
    '高脂血症':['hyperlipidemia','hypercholesterolemia'], '高胆固醇':['hypercholesterolemia'],
    '胃食管反流':['gastroesophageal reflux'], '反流性食管炎':['erosive esophagitis'],
    '过敏性鼻炎':['hay fever','allergic rhinitis'], '哮喘':['asthma'], '慢阻肺':['chronic obstructive'],
    '便秘':['constipation'], '细菌感染':['bacterial infection','bacteria'],
    '尿路感染':['urinary tract infection'], '真菌感染':['fungal','candidiasis'],
    '流感':['influenza'], '痛风':['gout'], '甲减':['hypothyroidism'], '骨质疏松':['osteoporosis'],
    '前列腺增生':['benign prostatic hyperplasia'], '青光眼':['glaucoma'], '痤疮':['acne'],
}


@lru_cache(maxsize=1)
def load_drugs():
    if not DATA_FILE.exists():return {'records':[],'imported_at':'','skipped':[]}
    return json.loads(DATA_FILE.read_text(encoding='utf-8'))


def reference_candidate(record):
    return {'name':record['name'],'purpose':'需由医生确认原文所列适应证，再评估是否适合该患者；此条仅为药品资料参考。',
            'checks':'核对禁忌、完整相互作用、相关检查、特殊人群及当地批准说明书。下方仅为英文原文节选，可能省略重要内容。',
            'url':record['source_url'],'aliases':[record['name'],record['english']],'risk_terms':[],
            'category':record['category'],'routes':record.get('routes',[]),'product_type':record.get('product_type',[]),
            'generic_names':record.get('generic_names',[]),
            'excerpts':record['excerpts'],'indications':record['excerpts'].get('indications_and_usage',record['excerpts'].get('purpose',''))[:1800],
            'boxed_warning':bool(record['excerpts'].get('boxed_warning')),'source_notice':record['notice']}


def retrieve_drug_candidates(assessment,selected='',limit=8):
    records=load_drugs()['records']
    if selected:
        return {item['id']:reference_candidate(item) for item in records if item['id']==selected}
    terms={english for chinese,english_list in ASSESSMENT_TERMS.items() if chinese in assessment for english in english_list}
    ranked=[]
    for item in records:
        excerpt=item['excerpts'].get('indications_and_usage',item['excerpts'].get('purpose','')).lower()
        # 重要警告药、注射和其他剂型先留在资料库，由医生明确选择后才参与核对。
        if item['excerpts'].get('boxed_warning') or item.get('routes')!=['ORAL']:
            continue
        score=sum(term in excerpt for term in terms)
        if item['name'] in assessment or item['english'].lower() in assessment.lower():score+=5
        if score:ranked.append((score,item))
    ranked.sort(key=lambda value:(-value[0],value[1]['name']))
    return {item['id']:reference_candidate(item) for _,item in ranked[:limit]}
