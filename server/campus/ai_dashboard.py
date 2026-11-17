from datetime import timedelta
from django.db.models import Count,Q,Avg
from django.utils import timezone
from .models import AIInvocation

COLORS=['#7f9c74','#b4a0c3','#c3a77c','#77a9a3','#9fadc5','#bc9c99']
def asset_chart(tables):
    rows=[]
    for i,row in enumerate(tables or []):
        value=max(0,int(row.get('rows',0)))
        rows.append({'name':row['name'],'rows':value,'color':COLORS[i%len(COLORS)]})
    total=sum(row['rows'] for row in rows);highest=max([r['rows'] for r in rows] or [1]);offset=0
    for row in rows:
        row['width']=round(100*row['rows']/max(1,highest),2)
        row['share']=round(100*row['rows']/max(1,total),1)
        row['arc']=round(100*row['rows']/max(1,total),4);row['offset']=-offset;offset+=row['arc']
    return {'rows':rows,'total':total}

def usage_data():
    today=timezone.localdate();now=timezone.now();first=today-timedelta(days=13)
    rows=AIInvocation.objects.all()
    totals=rows.aggregate(total=Count('id'),success=Count('id',filter=Q(success=True)),average=Avg('duration_ms'))
    today_rows=rows.filter(created_at__date=today)
    models=list(rows.values('provider','model').annotate(total=Count('id'),success=Count('id',filter=Q(success=True)),average=Avg('duration_ms')).order_by('-total','provider','model'))
    maximum=max([x['total'] for x in models] or [1])
    for row in models:
        row['failed']=row['total']-row['success'];row['width']=round(100*row['total']/maximum,2);row['rate']=round(100*row['success']/row['total'],1)
    trend=[]
    # Fixed 14-day bins in the configured Shanghai time zone; not browser UTC dates.
    from django.db.models.functions import TruncDate
    grouped=list(rows.filter(created_at__date__gte=first).annotate(day=TruncDate('created_at')).values('day','provider').annotate(count=Count('id')))
    counts={(x['day'],x['provider']):x['count'] for x in grouped}
    peak=max([sum(counts.get((first+timedelta(days=i),p),0) for p in ('ollama','deepseek')) for i in range(14)] or [1])
    peak=max(1,peak)
    for i in range(14):
        day=first+timedelta(days=i);local=counts.get((day,'ollama'),0);cloud=counts.get((day,'deepseek'),0)
        trend.append({'day':day.isoformat(),'label':day.strftime('%m/%d'),'local':local,'cloud':cloud,'local_h':round(100*local/peak,2),'cloud_h':round(100*cloud/peak,2)})
    totals.update(failed=totals['total']-totals['success'],today=today_rows.count(),local=rows.filter(provider='ollama').count(),cloud=rows.filter(provider='deepseek').count(),models=models,trend=trend,first=rows.order_by('created_at').first(),updated=now)
    return totals
