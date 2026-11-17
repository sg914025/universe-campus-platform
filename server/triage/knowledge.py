"""只检索 MedlinePlus 官方 XML 中允许复用的健康主题摘要。"""
import json
import re
from functools import lru_cache
from pathlib import Path
from .disease_aliases import DISEASE_ALIASES

DATA_FILE = Path(__file__).parent / 'data' / 'medlineplus.json'
GENETICS_FILE = DATA_FILE.with_name('medlineplus_genetics.json')
TOPICS = {
    'head': ['Headache', 'Dizziness and Vertigo', 'Eye Diseases', 'Ear Disorders'],
    'neck': ['Neck Injuries and Disorders', 'Sore Throat'],
    'chest': ['Chest Pain', 'Breathing Problems', 'Cough'],
    'abdomen': ['Abdominal Pain', 'Indigestion', 'Diarrhea', 'Nausea and Vomiting'],
    'back': ['Back Pain'], 'pelvis': ['Pelvic Pain', 'Hip Injuries and Disorders'],
    'arms': ['Shoulder Injuries and Disorders', 'Elbow Injuries and Disorders'],
    'hands': ['Hand Injuries and Disorders', 'Wrist Injuries and Disorders'],
    'legs': ['Knee Injuries and Disorders', 'Leg Injuries and Disorders', 'Ankle Injuries and Disorders', 'Foot Injuries and Disorders'],
}
ALIASES = {
    '头痛': 'Headache', '头疼': 'Headache', '头晕': 'Dizziness and Vertigo',
    '眼': 'Eye Diseases', '耳': 'Ear Disorders', '嗓': 'Sore Throat',
    '胸': 'Chest Pain', '呼吸': 'Breathing Problems', '咳': 'Cough',
    '肚': 'Abdominal Pain', '腹': 'Abdominal Pain', '胃': 'Indigestion',
    '腹泻': 'Diarrhea', '吐': 'Nausea and Vomiting', '腰': 'Back Pain', '背': 'Back Pain',
    '骨盆': 'Pelvic Pain', '肩': 'Shoulder Injuries and Disorders', '肘': 'Elbow Injuries and Disorders',
    '手': 'Hand Injuries and Disorders', '腕': 'Wrist Injuries and Disorders',
    '膝': 'Knee Injuries and Disorders', '腿': 'Leg Injuries and Disorders',
    '踝': 'Ankle Injuries and Disorders', '脚': 'Foot Injuries and Disorders',
}


@lru_cache(maxsize=1)
def load_knowledge():
    health=json.loads(DATA_FILE.read_text(encoding='utf-8')) if DATA_FILE.exists() else {'records':[],'imported_at':''}
    genetics=json.loads(GENETICS_FILE.read_text(encoding='utf-8')) if GENETICS_FILE.exists() else {'records':[],'imported_at':''}
    return {'records':health['records']+genetics['records'],'imported_at':health.get('imported_at',''),
            'health_topics':len(health['records']),'genetic_conditions':len(genetics['records']),
            'genetics_imported_at':genetics.get('imported_at','')}


def retrieve(part, text, limit=3):
    family = part.split('_')[-1]
    family = {'arm': 'arms', 'hand': 'hands', 'leg': 'legs'}.get(family, family)
    wanted = TOPICS.get(family, [])
    exact = {title for word, title in ALIASES.items() if word in text}
    disease_titles={title.lower() for word,titles in DISEASE_ALIASES.items() if word in text for title in titles}
    tokens = set(re.findall(r'[a-z]{3,}', text.lower()))
    ranked = []
    for record in load_knowledge()['records']:
        title = record['title']
        if record.get('kind')=='genetic_condition':
            # 不因普通头痛、腹痛、部位或单个英语泛词推测遗传病。
            titles=[title,*record.get('synonyms',[])]
            named=any(value.lower() in text.lower() for value in titles if len(value)>5)
            score=100 if title.lower() in disease_titles else 70 if named else 0
            if score:ranked.append((score,record))
            continue
        score = (20 if title in wanted else 0) + (35 if title in exact else 0)
        if title.lower() in disease_titles:score+=100
        score += len(tokens & set(re.findall(r'[a-z]{3,}', title.lower()))) * 4
        if score:
            ranked.append((score, record))
    ranked.sort(key=lambda item: (-item[0], item[1]['title']))
    if any(record['title'] in exact or record['title'].lower() in disease_titles for _,record in ranked):
        ranked=[item for item in ranked if item[1]['title'] in exact or item[1]['title'].lower() in disease_titles]
    return [record for _, record in ranked[:limit]]
