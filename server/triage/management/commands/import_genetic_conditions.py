import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from xml.etree import ElementTree
from django.core.management.base import BaseCommand,CommandError

SOURCE='https://medlineplus.gov/download/ghr-summaries.xml'
DATA_FILE=Path(__file__).resolve().parents[2]/'data'/'medlineplus_genetics.json'


class Command(BaseCommand):
    help='导入官方 MedlinePlus 遗传病描述、别名和遗传模式；不抓取图片或第三方全文。'
    def add_arguments(self,parser):
        parser.add_argument('--file',help='已下载的官方 XML 本地路径')
    def handle(self,*args,**options):
        if options.get('file'):
            raw=Path(options['file']).read_bytes()
        else:
            with urlopen(Request(SOURCE,headers={'User-Agent':'StudentTriageKnowledge/1.0'}),timeout=60) as response:
                if not response.geturl().startswith('https://medlineplus.gov/download/'):
                    raise CommandError('数据地址不正确。')
                raw=response.read(30_000_001)
        if len(raw)>30_000_000:
            raise CommandError('数据大小异常，保留旧数据。')
        root=ElementTree.fromstring(raw);ns={'n':root.tag[1:].split('}')[0]}
        records=[]
        for item in root.findall('n:health-condition-summary',ns):
            title=item.findtext('n:name','',ns);url=item.findtext('n:ghr-page','',ns)
            if not url.startswith('https://medlineplus.gov/genetics/condition/'):
                continue
            sections=[]
            for text in item.findall('n:text-list/n:text',ns):
                html=text.find('n:html',ns)
                if html is not None:sections.append(' '.join(' '.join(html.itertext()).split()))
            inheritance=[x.findtext('n:memo','',ns) for x in item.findall('n:inheritance-pattern-list/n:inheritance-pattern',ns)]
            summary=' '.join(sections)
            if inheritance:summary+=' Inheritance patterns: '+', '.join(inheritance)+'.'
            if not summary:continue
            records.append({'id':'genetics-'+item.get('id',''),'title':title,'url':url,'summary':summary,
                            'synonyms':[x.text for x in item.findall('n:synonym-list/n:synonym',ns) if x.text],
                            'kind':'genetic_condition','language':'English','reviewed':item.findtext('n:reviewed','',ns),
                            'attribution':'Source: MedlinePlus Genetics, National Library of Medicine.'})
        if len(records)<1000:
            raise CommandError('有效疾病数量异常，保留旧数据。')
        data={'source':SOURCE,'sha256':hashlib.sha256(raw).hexdigest(),'imported_at':datetime.now(timezone.utc).isoformat(),
              'license_note':'Public-domain MedlinePlus Genetics text summaries; no images or external articles.',
              'scope_note':'Genetic condition descriptions and inheritance; not proof of a genetic cause in any patient.',
              'records':records}
        DATA_FILE.parent.mkdir(parents=True,exist_ok=True)
        temporary=DATA_FILE.with_suffix('.new');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(DATA_FILE)
        self.stdout.write(f'Imported {len(records)} genetic condition descriptions and inheritance records.')
