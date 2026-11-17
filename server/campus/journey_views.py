import uuid,json
from datetime import timedelta,timezone as dt_timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import IntegrityError,OperationalError
from django.http import HttpResponse,JsonResponse
from django.shortcuts import render,get_object_or_404,redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET,require_POST,require_http_methods
from .models import Venue,VenueBooking,VenueWaitlist,TIME_SLOTS
from .booking_forms import BookingForm,slot_start,can_book
from . import waitlist
from .meaning import compare,fields
from .ui_language import context as ui_context,translate

SALT='universe-booking-preview-v1'

@never_cache
@login_required
@require_POST
def assistant_preview(request):
    from .task_assistant import draft_for
    try:
        if len(request.body)>10000:raise ValueError()
        data=json.loads(request.body)
        if not isinstance(data,dict) or set(data)!={'draft_key','venue_id'} or type(data['venue_id']) is not int:raise ValueError()
        draft=draft_for(request)
        if not draft or draft.get('key')!=data['draft_key']:raise ValueError()
        form=BookingForm({'day':draft.get('day'),'slot':draft.get('slot'),'request_key':draft['key']})
        if not form.is_valid():raise ValueError()
        venue=get_object_or_404(Venue,pk=data['venue_id'],kind=draft.get('kind'),active=True)
        if venue.kind=='study' and venue.building!=draft.get('building'):raise ValueError()
        selected=form.cleaned_data
        occupied=VenueBooking.objects.filter(day=selected['day'],slot=selected['slot'],status='reserved').filter(venue=venue).exists()
        personal=VenueBooking.objects.filter(day=selected['day'],slot=selected['slot'],status='reserved',user=request.user).exists()
        queue=VenueWaitlist.objects.filter(venue=venue,day=selected['day'],slot=selected['slot'])
        offer=queue.filter(status='offered',offered_until__gt=timezone.now()).first()
        queued=offer.user_id!=request.user.pk if offer else queue.filter(status='waiting').exists()
        language=ui_context(request)['ui_language']
        return JsonResponse({'available':not(occupied or personal or queued),'message':translate('预演只检查，不创建预约；确认提交时还会再次检查空位。',language)})
    except (ValueError,KeyError,TypeError,UnicodeDecodeError):return JsonResponse({'error':'Invalid or expired booking preview'},status=400)

@never_cache
@login_required
@require_http_methods(['GET','POST'])
def meaning_check(request):
    original=translated='';result=None
    if request.method=='POST':
        original=request.POST.get('original','').strip()[:2000];translated=request.POST.get('translated','').strip()[:2000]
        if original and translated:result=compare(original,translated,timezone.localdate())
    return render(request,'campus/journey/meaning.html',{'original':original,'translated':translated,'result':result})

@never_cache
@login_required
@require_POST
def preview(request,pk):
    venue=get_object_or_404(Venue,pk=pk,active=True)
    form=BookingForm(request.POST)
    if not form.is_valid():
        messages.error(request,'预约信息不完整或时段已开始，请重新查询。');return redirect('campus:booking-venue',pk)
    data=form.cleaned_data
    original=request.POST.get('original','').strip()[:2000];translated=request.POST.get('translated','').strip()[:2000]
    result=compare(original,translated,timezone.localdate()) if original and translated else None
    if bool(original)!=bool(translated):result={'status':'review','rows':[],'limited':True}
    candidate=fields(translated,timezone.localdate()) if translated else {}
    for key,value in [('day',data['day'].isoformat()),('time',data['slot']+':00'),('kind',venue.kind)]:
        if key in candidate and candidate[key]!=value:
            result=result or {'rows':[],'limited':True}
            result['status']='mismatch'
            result['rows'].append({'label':{'day':'日期','time':'开始时间','kind':'场地类型'}[key],'original':candidate[key],'translated':value,'state':'mismatch'})
    offer=VenueWaitlist.objects.filter(venue=venue,day=data['day'],slot=data['slot'],status='offered',offered_until__gt=timezone.now()).first()
    occupied=VenueBooking.objects.filter(venue=venue,day=data['day'],slot=data['slot'],status='reserved').exists()
    personal=VenueBooking.objects.filter(user=request.user,day=data['day'],slot=data['slot'],status='reserved').exists()
    held=bool(offer and offer.user_id!=request.user.pk)
    available=not(occupied or personal or held)
    if not occupied and not offer and VenueWaitlist.objects.filter(venue=venue,day=data['day'],slot=data['slot'],status='waiting').exists():available=False;held=True
    allowed=available and (not result or result['status']!='mismatch')
    needs_review=bool(result and result['status']=='review')
    token=signing.dumps({'user':request.user.pk,'venue':pk,'day':data['day'].isoformat(),'slot':data['slot'],'request_key':str(data['request_key']),'review':needs_review},salt=SALT) if allowed else ''
    return render(request,'campus/journey/preview.html',{'venue':venue,'day':data['day'],'slot':dict(TIME_SLOTS)[data['slot']],'result':result,'token':token,'available':available,'personal':personal,'held':held,'needs_review':needs_review,'slot_code':data['slot']})

@never_cache
@login_required
@require_POST
def commit(request):
    try:
        data=signing.loads(request.POST.get('token',''),salt=SALT,max_age=300)
        if data['user']!=request.user.pk or data.get('review') and request.POST.get('review_confirmed')!='yes':raise ValueError()
        form=BookingForm({'day':data['day'],'slot':data['slot'],'request_key':data['request_key']})
        if not form.is_valid():raise ValueError()
        venue=get_object_or_404(Venue,pk=data['venue'])
        record=waitlist.reserve(request.user,venue,**form.cleaned_data)
    except (signing.BadSignature,ValueError,KeyError,TypeError):
        messages.error(request,'预演已过期或信息未确认，请重新预演。');return redirect('campus:booking')
    except (IntegrityError,OperationalError):
        messages.error(request,'空位已变化或正在处理候补，请重新查询。');return redirect('campus:booking')
    return redirect('campus:service-card',record.pk)

@never_cache
@login_required
@require_GET
def card(request,pk):
    item=get_object_or_404(VenueBooking.objects.select_related('venue'),pk=pk,user=request.user)
    language=ui_context(request)['ui_language'];second=request.GET.get('second','ru' if language=='zh' else 'zh')
    if second not in ('zh','en','ru','ja'):second='zh'
    if second==language:second='en' if language!='en' else 'zh'
    codes=[language,second]
    labels=[('预约编号',str(item.pk)),('场地',item.venue.name),('场地类型',item.venue.get_kind_display()),('预约日期',item.day.isoformat()),('预约时段',item.get_slot_display()),('位置说明',item.venue.location or '位置尚未填写，请联系管理员确认'),('状态',item.get_status_display())]
    columns=[{'language':code,'name':{'zh':'中文','en':'English','ru':'Русский','ja':'日本語'}[code],
              'rows':[{'label':translate(label,code),'value':translate(str(value),code)} for label,value in labels]} for code in codes]
    return render(request,'campus/journey/card.html',{'item':item,'columns':columns,'second':second,'is_active':item.status=='reserved' and slot_start(item.day,item.slot)>timezone.now()})

@never_cache
@login_required
@require_GET
def calendar(request,pk):
    item=get_object_or_404(VenueBooking.objects.select_related('venue'),pk=pk,user=request.user)
    start=slot_start(item.day,item.slot);end=start+timedelta(hours=2)
    clean=lambda s:str(s).replace('\\','\\\\').replace('\r','').replace('\n','\\n').replace(';','\\;').replace(',','\\,')
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//UniVerse//Campus booking//EN','BEGIN:VEVENT',f'UID:booking-{item.pk}@universe.local',f'DTSTAMP:{timezone.now().astimezone(dt_timezone.utc):%Y%m%dT%H%M%SZ}',f'DTSTART:{start.astimezone(dt_timezone.utc):%Y%m%dT%H%M%SZ}',f'DTEND:{end.astimezone(dt_timezone.utc):%Y%m%dT%H%M%SZ}','SUMMARY:'+clean(item.venue.name),'LOCATION:'+clean(item.venue.location),'STATUS:'+('CONFIRMED' if item.status=='reserved' else 'CANCELLED'),'END:VEVENT','END:VCALENDAR']
    folded=[]
    for line in lines:
        part=''
        for ch in line:
            if len((part+ch).encode('utf-8'))>73:folded.append(part);part=' '+ch
            else:part+=ch
        folded.append(part)
    response=HttpResponse('\r\n'.join(folded)+'\r\n',content_type='text/calendar; charset=utf-8');response['Content-Disposition']=f'attachment; filename="universe-booking-{pk}.ics"';return response

@never_cache
@login_required
@require_http_methods(['GET','POST'])
def queue(request):
    if request.method=='POST':
        try:
            pk=int(request.POST.get('entry','0'));action=request.POST.get('action')
            row=get_object_or_404(VenueWaitlist,pk=pk,user=request.user)
            if action=='refresh':waitlist.refresh(row)
            elif action=='leave':waitlist.leave(row)
            elif action=='claim':
                record=waitlist.claim(row,request.user);return redirect('campus:service-card',record.pk)
            else:raise ValueError()
        except (ValueError,IntegrityError,OperationalError):messages.error(request,'候补状态已变化，请刷新后重试。')
        return redirect('campus:waitlist')
    rows=list(VenueWaitlist.objects.filter(user=request.user).select_related('venue').order_by('-created_at')[:50])
    for row in rows:
        row.position=VenueWaitlist.objects.filter(venue=row.venue,day=row.day,slot=row.slot,status__in=['waiting','offered'],created_at__lte=row.created_at).count() if row.status in ('waiting','offered') else None
        row.live=row.status in ('waiting','offered')
        row.claimable=row.status=='offered' and row.offered_until and row.offered_until>timezone.now()
    return render(request,'campus/journey/waitlist.html',{'rows':rows})

@never_cache
@login_required
@require_POST
def join_queue(request,pk):
    venue=get_object_or_404(Venue,pk=pk,active=True);form=BookingForm(request.POST)
    try:
        if not form.is_valid():raise ValueError()
        waitlist.join(request.user,venue,form.cleaned_data['day'],form.cleaned_data['slot'])
    except (ValueError,IntegrityError,OperationalError):messages.error(request,'无法加入候补：请检查日期、个人冲突，空闲场地请直接预约。')
    return redirect('campus:waitlist')

from .management_views import role_required

@never_cache
@role_required('booking')
@require_http_methods(['GET','POST'])
def queue_admin(request):
    if request.method=='POST':
        try:
            row=get_object_or_404(VenueWaitlist,pk=int(request.POST.get('entry','0')))
            waitlist.refresh(row)
            from .audit import record_event
            record_event(request.user,'booking','刷新候补队列',row)
        except (ValueError,IntegrityError,OperationalError):messages.error(request,'候补状态已变化，请刷新后重试。')
        return redirect('campus:waitlist-admin')
    return render(request,'campus/journey/queue_admin.html',{'rows':VenueWaitlist.objects.filter(status__in=['waiting','offered']).select_related('venue','user')[:100]})
