import io
import json
import re
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from django.core.management.base import BaseCommand, CommandError
from triage.knowledge import DATA_FILE, load_knowledge


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)


def fetch(url, maximum):
    request = Request(url, headers={'User-Agent': 'StudentTriageKnowledge/1.0'})
    with urlopen(request, timeout=60) as response:
        if not response.geturl().startswith('https://medlineplus.gov/'):
            raise CommandError('数据地址必须属于 MedlinePlus 官方网站。')
        result = response.read(maximum + 1)
    if len(result) > maximum:
        raise CommandError('官方数据超过预设大小，请人工检查。')
    return result


class Command(BaseCommand):
    help = '从官方 XML 更新健康主题摘要；不抓取第三方药品、百科或图片。'

    def handle(self, *args, **options):
        page = fetch('https://medlineplus.gov/xml.html', 2_000_000).decode('utf-8')
        links = re.findall(r'https://medlineplus.gov/xml/mplus_topics_compressed_\d{4}-\d{2}-\d{2}\.zip', page)
        if not links:
            raise CommandError('未找到官方数据包。')
        url = max(links)
        archive = zipfile.ZipFile(io.BytesIO(fetch(url, 20_000_000)))
        member = next((item for item in archive.infolist() if item.filename.endswith('.xml')), None)
        if member is None or member.file_size > 70_000_000:
            raise CommandError('数据包格式不正确。')
        tree = ElementTree.fromstring(archive.read(member))
        records = []
        for topic in tree.findall('health-topic'):
            if topic.get('language') != 'English':
                continue
            summary = topic.find('full-summary')
            if summary is None:
                continue
            parser = PlainText()
            parser.feed(''.join(summary.itertext()))
            text = ' '.join(' '.join(parser.text).split())
            if text and topic.get('url', '').startswith('https://medlineplus.gov/'):
                records.append({'id': topic.get('id'), 'title': topic.get('title'), 'url': topic.get('url'),
                    'summary': text, 'language': 'English', 'attribution': 'Source: MedlinePlus, National Library of Medicine.'})
        if len(records) < 100:
            raise CommandError('有效摘要数量异常，保留旧知识库。')
        data = {'source': url, 'imported_at': datetime.now(timezone.utc).isoformat(),
            'license_note': 'Only public-domain MedlinePlus health-topic summaries. No linked third-party content.', 'records': records}
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = DATA_FILE.with_suffix('.new')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(DATA_FILE)
        load_knowledge.cache_clear()
        self.stdout.write(self.style.SUCCESS(f'Imported {len(records)} English summaries from {url}'))
