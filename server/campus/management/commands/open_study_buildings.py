from django.core.management.base import BaseCommand
from django.db import transaction
from campus.models import Venue


class Command(BaseCommand):
    help='开放所有自习资源，并为 A/B/C 楼和图书馆补充各 20 个示例座位。'

    @transaction.atomic
    def handle(self,*args,**options):
        created=0
        for code,label in [('A','A 楼'),('B','B 楼'),('C','C 楼'),('library','图书馆')]:
            for number in range(1,21):
                _,added=Venue.objects.get_or_create(
                    kind='study',building=code,name=f'{label} · 示例 {number:02d} 号座位',is_demo=True,
                    defaults={'active':True,'location':f'{label} · 示例自习区域','description':'示例自习座位，按两小时时段预约；请以学校实际开放安排为准。'})
                created+=added
        reopened=Venue.objects.filter(kind='study',active=False).update(active=True)
        self.stdout.write(self.style.SUCCESS(f'已新增 {created} 个示例座位，重新开放 {reopened} 个自习资源。'))
