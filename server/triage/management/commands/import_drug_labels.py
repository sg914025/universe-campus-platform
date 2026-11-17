import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,urlparse
from urllib.request import urlopen,Request
from urllib.error import HTTPError
from django.core.management.base import BaseCommand,CommandError
from triage.drug_roster import roster

DATA_FILE=Path(__file__).resolve().parents[2]/'data'/'drug_labels.json'
SECTIONS=('indications_and_usage','purpose','contraindications','warnings','warnings_and_cautions','boxed_warning','drug_interactions','pregnancy','pregnancy_or_breast_feeding','use_in_specific_populations')
GENERIC_VARIANTS={
    'cefpodoxime':['cefpodoxime proxetil'],'fosfomycin':['fosfomycin tromethamine','fosfomycin disodium'],
    'oseltamivir':['oseltamivir phosphate'],'miconazole':['miconazole nitrate'],
    'ipratropium':['ipratropium bromide'],'tiotropium':['tiotropium bromide'],
    'fluticasone':['fluticasone propionate'],'beclomethasone':['beclomethasone dipropionate'],
    'mometasone':['mometasone furoate'],'olmesartan':['olmesartan medoxomil'],
    'dabigatran':['dabigatran etexilate'],'betamethasone':['betamethasone dipropionate','betamethasone valerate'],
    'triamcinolone':['triamcinolone acetonide'],'ferrous gluconate':['ferrous gluconate dihydrate'],
}


def normalized(value):
    value=re.sub(r'[^a-z0-9 ]',' ',value.lower())
    for salt in ('hydrochloride','dihydrochloride','hydrobromide','sulfate','sulphate','sodium','potassium','calcium','fumarate','succinate','tartrate','maleate','mesylate','besylate','trihydrate','monohydrate','hydrate','anhydrous','usp'):
        value=re.sub(r'\b'+salt+r'\b',' ',value)
    return ' '.join(value.split())


def get_label(item,cache):
    # 精确匹配通用名及盐型，不把复方制剂当成单方药。
    query='openfda.generic_name:"'+item['english']+'"'
    partial_url='https://api.fda.gov/drug/label.json?'+urlencode({'search':query,'limit':20,'sort':'effective_time:desc'})
    exact_query='openfda.generic_name.exact:"'+('alendronate sodium' if item['english']=='alendronate' else item['english']).upper()+'"'
    url='https://api.fda.gov/drug/label.json?'+urlencode({'search':exact_query,'limit':3,'sort':'effective_time:desc'})
    cache_file=cache/(item['id']+'.json') if cache else None
    for attempt in range(2):
        try:
            if cache_file and cache_file.exists():
                raw=cache_file.read_bytes()
                cached=json.loads(raw)
                if isinstance(cached,dict) and 'payload' in cached:
                    url=cached['url'];raw=json.dumps(cached['payload']).encode('utf-8')
                else:
                    url=partial_url
            else:
                request=Request(url,headers={'User-Agent':'StudentTriageDrugReferences/1.0'})
                with urlopen(request,timeout=35) as response:
                    if urlparse(response.geturl()).hostname!='api.fda.gov':
                        raise ValueError('Unexpected source host')
                    raw=response.read(8_000_001)
                if len(raw)>8_000_000:
                    raise ValueError('Label response exceeds bound')
                if cache_file:
                    cache_file.write_text(json.dumps({'url':url,'payload':json.loads(raw)}),encoding='utf-8')
            data=json.loads(raw)
            wanted={normalized(value) for value in [item['english'],*GENERIC_VARIANTS.get(item['english'],[])]}
            selected=None
            for label in data.get('results',[]):
                fda=label.get('openfda',{})
                names=fda.get('generic_name',[])
                has_indication=bool(label.get('indications_and_usage') or label.get('purpose'))
                if has_indication and names and all(normalized(name) in wanted for name in names) and any(kind.startswith('HUMAN ') for kind in fda.get('product_type',[])):
                    selected=label;break
            if selected is None:
                return None,{'name':item['name'],'reason':'没有找到匹配的单方人用药标签'}
            setid=selected.get('set_id','')
            if not re.fullmatch(r'[a-f0-9-]{36}',setid):
                raise ValueError('Invalid source label identifier')
            excerpts={key:' '.join(selected.get(key,[]))[:5000] for key in SECTIONS if selected.get(key)}
            if not (excerpts.get('indications_and_usage') or excerpts.get('purpose')):
                return None,{'name':item['name'],'reason':'标签缺少适应证或用途字段'}
            return {**item,'setid':setid,'generic_names':selected['openfda'].get('generic_name',[]),
                    'routes':selected['openfda'].get('route',[]),'product_type':selected['openfda'].get('product_type',[]),
                    'pharmacologic_classes':selected['openfda'].get('pharm_class_epc',[]),
                    'effective_time':selected.get('effective_time',''),'excerpts':excerpts,
                    'source_url':'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid='+setid,
                    'api_source':url,'source_sha256':hashlib.sha256(raw).hexdigest(),
                    'attribution':'Source: openFDA / DailyMed, U.S. Food and Drug Administration and National Library of Medicine.',
                    'notice':'英文原文节选，可能省略重要内容；核对完整原文及当地批准的实际说明书。'},None
        except Exception as error:
            if attempt==0:
                if isinstance(error,HTTPError) and error.code==404:
                    url=partial_url
                time.sleep(1)
            else:
                return None,{'name':item['name'],'reason':type(error).__name__}


class Command(BaseCommand):
    help='导入中文常用西药目录对应的 FDA 单方人用药标签节选；无患者资料发往外网。'
    def add_arguments(self,parser):
        parser.add_argument('--cache',help='本地原始响应缓存目录')
    def handle(self,*args,**options):
        cache=Path(options['cache']).resolve() if options.get('cache') else None
        if cache:cache.mkdir(parents=True,exist_ok=True)
        records=[];skipped=[];items=roster()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(get_label,item,cache) for item in items]
            for index,job in enumerate(as_completed(jobs),1):
                record,error=job.result()
                if record:records.append(record)
                if error:skipped.append(error)
                if index%20==0:self.stdout.write(f'Checked {index}/{len(items)}, matched {len(records)} labels');self.stdout.flush()
        if len(records)<50:
            raise CommandError('有效标签过少，保留旧药品资料。')
        data={'source':'https://open.fda.gov/apis/drug/label/','license':'openFDA CC0 public data; no device GMDN content.',
              'imported_at':datetime.now(timezone.utc).isoformat(),'roster_count':len(items),
              'coverage_note':'中文常用西药目录中的有效匹配，不等于所有药品，不代表中国上市或处方批准。',
              'records':sorted(records,key=lambda item:(item['category'],item['name'])),'skipped':skipped}
        DATA_FILE.parent.mkdir(parents=True,exist_ok=True)
        temporary=DATA_FILE.with_suffix('.new');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(DATA_FILE)
        self.stdout.write(f'Imported {len(records)} matched drug labels; {len(skipped)} unmatched or unavailable entries.')
