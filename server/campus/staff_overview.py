from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from .management_views import role_required
from .models import StaffAuditEvent,VenueBooking,Venue
from 帖子.models import report,risk_alert,recharge
from 跑腿.models import task,question
from triage.models import Consultation,CaseConference


@role_required('superadmin')
@require_GET
def overview(request):
    now=timezone.now()
    cards=[
        ('举报待审核',report.objects.filter(status='pending').count(),'campus:dashboard'),
        ('风险待复核',risk_alert.objects.filter(status='pending').count(),'campus:risk_alerts'),
        ('跑腿咨询待回复',question.objects.filter(status='pending').count(),'campus:admin_questions'),
        ('充值待审核',recharge.objects.filter(status='pending').count(),'campus:recharges'),
        ('医生待回复',Consultation.objects.filter(status='pending').count(),None),
        ('会诊待接受',CaseConference.objects.filter(status='pending').count(),None),
        ('今日场地预约',VenueBooking.objects.filter(day=timezone.localdate(),status='reserved').count(),'campus:booking-admin'),
        ('进行中的跑腿',task.objects.filter(status__in=['open','accepted','delivered']).count(),'campus:admin_errands'),
    ]
    from .security_views import context as security_context
    data=security_context(request,'operations')
    data.update({
        'cards':[{'title':title,'count':count,'url':reverse(name) if name else '', 'restricted':name is None} for title,count,name in cards],
        'overdue_health':Consultation.objects.filter(status='pending',created_at__lt=now-timedelta(hours=24)).count(),
        'overdue_questions':question.objects.filter(status='pending',created_at__lt=now-timedelta(hours=24)).count(),
        'open_venues':Venue.objects.filter(active=True).count(),
        'staff_events':StaffAuditEvent.objects.select_related('actor')[:8],
        'user_count':get_user_model().objects.filter(is_active=True).count(),
    })
    return render(request,'campus/management/overview.html',data)


@role_required('superadmin')
@require_GET
def audit_log(request):
    module=request.GET.get('module','')
    records=StaffAuditEvent.objects.all()
    if module in ('doctor','campus','booking','superadmin'):records=records.filter(module=module)
    else:module=''
    return render(request,'campus/management/audit.html',{'page':Paginator(records,25).get_page(request.GET.get('page')),'module':module})
