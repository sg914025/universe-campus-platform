import re
from django.core.management.base import BaseCommand
from django.db import transaction
from campus.models import Venue

class Command(BaseCommand):
    help='为校园内部模型补充示例运动资源，并将已有示例自习座位分布到两层。'
    @transaction.atomic
    def handle(self,*args,**kwargs):
        floors=0
        for v in Venue.objects.filter(kind='study',is_demo=True,building__in=['A','B','C','library']):
            number=re.search(r'示例\s*(\d+)\s*号座位',v.name)
            if number:
                floor=1 if int(number[1])<=10 else 2
                if v.floor!=floor:v.floor=floor;v.save(update_fields=['floor']);floors+=1
        Venue.objects.filter(is_demo=True,kind__in=['basketball','badminton'],map_area='').update(map_area='gym',floor=2)
        created=0
        for kind,label,amount,floor,area in [('table_tennis','乒乓球台',8,1,'gym'),('basketball','室内篮球场',2,2,'gym'),('football','室外足球场',1,1,'outdoor')]:
            for number in range(1,amount+1):
                _,added=Venue.objects.get_or_create(kind=kind,name=f'{label} · 示例 {number:02d} 号',map_area=area,is_demo=True,
                    defaults={'floor':floor,'active':True,'location':'体育馆 · 示例区域' if area=='gym' else '室外运动区 · 示例区域','description':'校园模型展示用示例资源，按时段预约，以学校实际安排为准。'})
                created+=added
        self.stdout.write(f'Created {created} demo sports resources; assigned {floors} study resources to floors. Existing bookings preserved.')
