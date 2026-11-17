import uuid
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError,OperationalError,transaction
from django.shortcuts import render,redirect,get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET,require_POST,require_http_methods
from .management_views import role_required
booking_only = role_required('booking')
from .models import Venue,VenueBooking,VenueWaitlist,VENUE_TYPES,TIME_SLOTS
from .models import STUDY_BUILDINGS
from .attendance import bookable
from . import waitlist
from .booking_forms import BookingForm,VenueForm,can_book,slot_start

def day_context(request):
    today=timezone.localdate();last=today+timedelta(days=14)
    raw=request.GET.get('day','') if request.method=='GET' else request.POST.get('day','')
    try:day=parse_date(raw)
    except ValueError:day=None
    if day is None or not today<=day<=last:day=today
    return {'day':day,'today':today,'last_day':last}

@never_cache
@require_GET
def index(request):
    context=day_context(request)
    category=request.GET.get('kind','')
    venues=Venue.objects.filter(active=True)
    if category in dict(VENUE_TYPES):venues=venues.filter(kind=category)
    else:category=''
    building=request.GET.get('building','') if category=='study' else ''
    if building not in dict(STUDY_BUILDINGS):building=''
    buildings=[{'code':code,'label':label,'count':Venue.objects.filter(active=True,kind='study',building=code).count()} for code,label in STUDY_BUILDINGS]
    if category=='study':
        venues=venues.filter(building=building) if building else venues.none()
    elif not category:venues=venues.exclude(kind='study')
    occupied={}
    for venue_id,slot in VenueBooking.objects.filter(day=context['day'],status='reserved').values_list('venue_id','slot'):
        occupied.setdefault(venue_id,set()).add(slot)
    holds=VenueWaitlist.objects.filter(day=context['day'],status='offered',offered_until__gt=timezone.now())
    if request.user.is_authenticated:holds=holds.exclude(user=request.user)
    for venue_id,slot in holds.values_list('venue_id','slot'):occupied.setdefault(venue_id,set()).add(slot)
    for venue in venues:
        venue.available_count=sum(bookable(venue,context['day'],code) and code not in occupied.get(venue.pk,set()) for code,_ in TIME_SLOTS)
    return render(request,'campus/booking/index.html',{**context,'venues':venues,'kinds':VENUE_TYPES,'kind':category,'building':building,'buildings':buildings})

@never_cache
@require_http_methods(['GET','POST'])
def venue_detail(request,pk):
    venue=get_object_or_404(Venue,pk=pk,active=True)
    context=day_context(request)
    if request.method=='POST':
        if not request.user.is_authenticated:return redirect('/register/?next='+request.path)
        form=BookingForm(request.POST,venue=venue)
        if form.is_valid():
            data=form.cleaned_data
            previous=VenueBooking.objects.filter(user=request.user,request_key=data['request_key']).first()
            if previous is not None:
                return redirect('campus:booking-mine')
            try:
                with transaction.atomic():
                    if not Venue.objects.filter(pk=venue.pk,active=True).exists():
                        form.add_error(None,'该场地已暂停预约，请选择其他场地。')
                    else:
                        waitlist.reserve(request.user,venue,**data)
            except IntegrityError:
                form.add_error(None,'该时段刚被预约，或你已有同时段预约，请选择其他时段。')
            except OperationalError as error:
                if 'locked' not in str(error).lower():raise
                form.add_error(None,'当前请求较多，请稍后重试，暂未生成新预约。')
            else:
                if not form.errors:
                    messages.success(request,'预约已保存，可在“我的预约”查看或取消。')
                    return redirect('campus:booking-mine')
    else:form=BookingForm(initial={'day':context['day'],'slot':request.GET.get('slot') if request.GET.get('slot') in dict(TIME_SLOTS) else None,'request_key':uuid.uuid4()})
    occupied=set(venue.bookings.filter(day=context['day'],status='reserved').values_list('slot',flat=True))
    personal=set(VenueBooking.objects.filter(user=request.user,day=context['day'],status='reserved').values_list('slot',flat=True)) if request.user.is_authenticated else set()
    holds={row.slot:row.user_id for row in VenueWaitlist.objects.filter(venue=venue,day=context['day'],status='offered',offered_until__gt=timezone.now())}
    slots=[]
    for code,label in TIME_SLOTS:
        reason='候补名额保留中' if code in holds and holds[code]!=request.user.pk else '已被预约' if code in occupied else '你已有同时段预约' if code in personal else '已开始／不可预约' if not bookable(venue,context['day'],code) else '可预约'
        slots.append({'code':code,'label':label,'available':reason=='可预约','reason':reason,'can_wait':bookable(venue,context['day'],code) and code not in personal and (code in occupied or code in holds)})
    return render(request,'campus/booking/detail.html',{**context,'venue':venue,'form':form,'slots':slots})

@never_cache
@login_required
@require_GET
def mine(request):
    records=VenueBooking.objects.filter(user=request.user).select_related('venue')
    page=Paginator(records,12).get_page(request.GET.get('page'))
    for item in page:item.can_cancel=item.status=='reserved' and slot_start(item.day,item.slot)>timezone.now()
    return render(request,'campus/booking/mine.html',{'page':page})

@login_required
@require_POST
def cancel(request,pk):
    item=get_object_or_404(VenueBooking,pk=pk,user=request.user)
    if item.status=='reserved' and slot_start(item.day,item.slot)>timezone.now():
        waitlist.cancel_booking(request.user,pk)
        messages.success(request,'预约已取消，该时段可以重新预约。')
    else:messages.info(request,'该预约已取消或时段已经开始。')
    return redirect('campus:booking-mine')

@never_cache
@booking_only
@require_http_methods(['GET','POST'])
def management(request):
    form=VenueForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        from .audit import record_event
        with transaction.atomic():
            added_venue=form.save()
            record_event(request.user,'booking','新增场地',added_venue)
        messages.success(request,'场地已添加。');return redirect('campus:booking-admin')
    from django.db.models import Q
    from .attendance import release_due,slot_end
    release_due()
    records=VenueBooking.objects.select_related('venue','user','released_by').order_by('-created_at')
    day=request.GET.get('day','')
    try:parsed=parse_date(day)
    except ValueError:parsed=None
    if parsed:records=records.filter(day=parsed)
    else:day=''
    state=request.GET.get('state','')
    queries={
        'waiting':Q(status='reserved',checked_in_at__isnull=True,checkin_deadline__isnull=False),
        'checked':Q(status='reserved',checked_in_at__isnull=False),
        'no_show':Q(status='no_show'),
        'released':Q(status='released'),
        'cancelled':Q(status='cancelled'),
        'exempt':Q(status='reserved',checkin_deadline__isnull=True,checked_in_at__isnull=True)}
    counts={key:records.filter(query).count() for key,query in queries.items()}
    if state in queries:records=records.filter(queries[state])
    else:state=''
    page=Paginator(records,20).get_page(request.GET.get('page'))
    for item in page:
        item.attendance_label='超时未到' if item.status=='no_show' else '管理员已释放' if item.status=='released' else '已取消' if item.status=='cancelled' else '已签到' if item.checked_in_at else '待签到' if item.checkin_deadline else '无需签到'
        item.can_release=item.status=='reserved' and item.venue.kind=='study' and slot_end(item.day,item.slot)>timezone.now()
    queue_count=VenueWaitlist.objects.filter(status__in=['waiting','offered']).count()
    return render(request,'campus/booking/manage.html',{'venues':Venue.objects.all(),'form':form,'page':page,'day':day,'state':state,'attendance_counts':counts,'queue_count':queue_count,'attendance_admin':True})

@booking_only
@require_POST
def release_seat(request,pk):
    from .attendance import manual_release
    get_object_or_404(VenueBooking,pk=pk)
    try:
        changed=manual_release(request.user,pk,request.POST.get('reason',''),request.POST.get('confirm_checked_in')=='yes')
        if changed:messages.success(request,'座位已释放，操作人与原因已记录。')
        else:messages.info(request,'该预约已释放、已结束或不属于自习座位，未重复操作。')
    except ValueError as error:messages.error(request,str(error))
    from urllib.parse import urlencode
    return redirect(reverse('campus:booking-admin')+'?'+urlencode({'day':request.POST.get('day',''),'state':request.POST.get('state','')}))

@never_cache
@booking_only
@require_http_methods(['GET','POST'])
def edit_venue(request,pk):
    venue=get_object_or_404(Venue,pk=pk)
    form=VenueForm(request.POST if request.method=='POST' else None,instance=venue)
    if request.method=='POST' and form.is_valid():
        form.save();messages.success(request,'场地设置已保存。');return redirect('campus:booking-admin')
    return render(request,'campus/booking/edit.html',{'form':form,'venue':venue})

from .audit import audit_change
edit_venue=audit_change('booking','campus.Venue',('name','kind','building','floor','map_area','location','description','active','is_demo'),'更新场地设置')(edit_venue)
