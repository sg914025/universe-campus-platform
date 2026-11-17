"""预约通知的只读后台。制作：UniVerse Team。"""
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET
from .management_views import role_required
from .models import BookingNotice

@role_required('booking')
@require_GET
def index(request):
    rows=BookingNotice.objects.select_related('user','booking__venue','waitlist__venue','waitlist__booking').order_by('-created_at','-pk')
    filters={key:request.GET.get(key,'').strip()[:150] for key in ['day','kind','read','confirmation','q']}
    try:day=parse_date(filters['day'])
    except ValueError:day=None
    if day:rows=rows.filter(created_at__date=day)
    else:filters['day']=''
    if filters['kind'] in dict(BookingNotice._meta.get_field('kind').choices):rows=rows.filter(kind=filters['kind'])
    else:filters['kind']=''
    if filters['q']:rows=rows.filter(user__username__icontains=filters['q'])
    if filters['read'] in ('yes','no'):rows=rows.filter(is_read=filters['read']=='yes')
    else:filters['read']=''
    now=timezone.now()
    states={'pending':Q(waitlist__status='offered',waitlist__offered_until__gt=now),'confirmed':Q(waitlist__status='claimed'),'expired':Q(waitlist__status='expired')|Q(waitlist__status='offered',waitlist__offered_until__lte=now),'left':Q(waitlist__status='cancelled'),'ineligible':Q(waitlist__status='ineligible')}
    if filters['confirmation'] in states:rows=rows.filter(kind='waitlist_offer').filter(states[filters['confirmation']])
    else:filters['confirmation']=''
    counts={'total':rows.count(),'read':rows.filter(is_read=True).count(),'unread':rows.filter(is_read=False).count(),'confirmed':rows.filter(kind='waitlist_offer',waitlist__status='claimed').count()}
    page=Paginator(rows,20).get_page(request.GET.get('page'))
    for row in page:
        row.resource=row.waitlist if row.kind=='waitlist_offer' else row.booking
        row.confirmation_label='不适用';row.confirmed_at=None;row.offer_deadline=None;row.confirmed_booking=None
        if row.kind=='waitlist_offer':
            queue=row.waitlist
            if not queue:row.confirmation_label='关联候补记录已删除'
            else:
                row.confirmation_label='已确认预约' if queue.status=='claimed' else '已过期' if queue.status=='expired' or (queue.status=='offered' and (not queue.offered_until or queue.offered_until<=now)) else '已退出' if queue.status=='cancelled' else '同时间已有预约' if queue.status=='ineligible' else '待本人确认' if queue.status=='offered' else '候补中'
                row.confirmed_at=queue.claimed_at;row.offer_deadline=queue.offered_until;row.confirmed_booking=queue.booking
    query=request.GET.copy();query.pop('page',None)
    return render(request,'campus/booking/notices.html',{'page':page,'filters':filters,'counts':counts,'filter_query':query.urlencode(),'attendance_admin':True})
