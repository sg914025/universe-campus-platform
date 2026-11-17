import json,uuid
from datetime import timedelta,date
from django.db import IntegrityError,OperationalError,transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET,require_POST
from django.contrib.auth.decorators import login_required
from .models import Venue,VenueBooking,VenueWaitlist,TIME_SLOTS,VENUE_TYPES
from .booking_forms import BookingForm,can_book
from .models import STUDY_BUILDINGS
from .task_intent import extract
from .companion_chat import answer,task_request,validate_history,ModelUnavailable,MODEL
from . import companion_weather, companion_external, waitlist, service_plans
from .ui_language import translate,context

SESSION_KEY='universe_task_draft_v1'
TTL=1200


def t(request,text):return translate(text,context(request)['ui_language'])
def error(request,text,status=400):return JsonResponse({'error':t(request,text)},status=status)
def access(request):
    if not request.user.is_authenticated or not request.user.is_active:
        return error(request,'请先登录校园账号，再使用办事向导。',401)


def payload(request):
    if len(request.body)>60000:raise ValueError()
    data=json.loads(request.body)
    if not isinstance(data,dict):raise ValueError()
    return data


def draft_for(request):
    draft=request.session.get(SESSION_KEY,{})
    if not isinstance(draft,dict) or draft.get('user')!=request.user.pk or draft.get('expires',0)<timezone.now().timestamp():return {}
    return draft


def navigation(request,intent):
    rows={
        'friends':('双方互相关注后就能私信交流，我带你去交友广场。',[('去认识同学','campus:friends')]),
        'help':('可以发布跑腿需求或帮助同学。涉及付款的订单，请在发布页面核对并提交。',[('去发布需求','campus:errand_create'),('接单广场','campus:errands')]),
        'health':('我可以带你进入导诊，先整理不适，再选择线上咨询或门诊预约。急诊无需预约。',[('了解导诊服务','guide')]),
        'services':('你的订单、预约和回复都可以在“我的服务”查看。',[('我的服务','my-services')]),
        'manage':('查看已有预约后，可以在“我的预约”页面取消。这里不会自动取消预约。',[('我的预约','campus:booking-mine'),('我的服务','my-services')]),
    }
    message,links=rows[intent]
    return {'phase':'navigate','intent':intent,'message':t(request,message),'actions':[{'label':t(request,label),'url':reverse(route)} for label,route in links]}


def render_state(request,draft,note=None,mode='rules'):
    today=timezone.localdate()
    visible=service_plans.active(request.user) or service_plans.CampusServicePlan.objects.filter(user=request.user).first()
    if draft.get('plan_id') and visible and visible.pk!=draft['plan_id']:draft={}
    result={'draft':{key:draft[key] for key in ('kind','building','day','slot') if draft.get(key)},'draft_key':draft.get('key',''),'plan_linked':bool(draft.get('plan_id')),
        'external_ai_ready':companion_external.configured(),'mode':mode,'today':today.isoformat(),'last_day':(today+timedelta(days=14)).isoformat(),'venues':[],'slots':[],'actions':[]}
    if visible:result['plan']=service_plans.serialize(request,visible)
    if draft.get('confirmed'):
        record=VenueBooking.objects.filter(pk=draft['confirmed'],user=request.user).select_related('venue').first()
        if record:
            result.update(phase='done',intent='booking',message=t(request,'预约已保存，可以到“我的服务”查看或取消。'),receipt={'id':record.pk,'venue':record.venue.name,'day':record.day.isoformat(),'slot':record.get_slot_display(),'status':t(request,record.get_status_display())},actions=[{'label':t(request,'多语办事卡'),'url':reverse('campus:service-card',args=[record.pk])},{'label':t(request,'我的服务'),'url':reverse('my-services')},{'label':t(request,'我的预约'),'url':reverse('campus:booking-mine')}])
            return result
    if not draft.get('kind'):
        result.update(phase='ask_kind',message=t(request,note or '你好！学习、翻译、写作和日常问题都可以问我，也可以一起办理校园场地预约。'))
    elif draft.get('kind')=='study' and draft.get('building') not in dict(STUDY_BUILDINGS):
        result.update(phase='ask_building',message=t(request,'先选择自习楼栋，再选择座位和时段。'),buildings=[{'value':code,'label':t(request,label)} for code,label in STUDY_BUILDINGS])
    elif not draft.get('day'):
        result.update(phase='ask_day',message=t(request,note or '想预约哪一天？可以说“明天”，也可以直接选择日期。'))
    else:
        selected_day=date.fromisoformat(draft['day'])
        venues=Venue.objects.filter(kind=draft['kind'],active=True).order_by('name','pk')
        if draft['kind']=='study':venues=venues.filter(building=draft['building'])
        occupied={}
        for venue_id,slot in VenueBooking.objects.filter(day=selected_day,status='reserved',venue__in=venues).values_list('venue_id','slot'):occupied.setdefault(slot,set()).add(venue_id)
        personal=set(VenueBooking.objects.filter(user=request.user,day=selected_day,status='reserved').values_list('slot',flat=True))
        for code,label in TIME_SLOTS:
            count=0 if code in personal or not can_book(selected_day,code) else sum(venue.pk not in occupied.get(code,set()) for venue in venues)
            holds=VenueWaitlist.objects.filter(venue__in=venues,day=selected_day,slot=code,status='offered',offered_until__gt=timezone.now()).exclude(user=request.user).values_list('venue_id',flat=True)
            count=max(0,count-sum(vid not in occupied.get(code,set()) for vid in holds))
            result['slots'].append({'value':code,'label':label,'count':count})
        if not draft.get('slot'):
            result.update(phase='ask_slot',message=t(request,note or '请选择具体时段。场地按固定两小时时段预约，我不会替你默认选择。'))
        else:
            held_ids=VenueWaitlist.objects.filter(venue__in=venues,day=selected_day,slot=draft['slot'],status='offered',offered_until__gt=timezone.now()).exclude(user=request.user).values_list('venue_id',flat=True)
            available=venues.exclude(pk__in=occupied.get(draft['slot'],set())).exclude(pk__in=held_ids) if draft['slot'] not in personal and can_book(selected_day,draft['slot']) else venues.none()
            for venue in available[:8]:
                result['venues'].append({'id':venue.pk,'name':venue.name,'label':t(request,venue.get_kind_display())+' #'+str(venue.pk),'day':draft['day'],'slot':dict(TIME_SLOTS)[draft['slot']]})
            result.update(phase='choose_venue',message=t(request,note or ('找到以下空位。请选择场地并核对信息，点击确认后才会预约。' if result['venues'] else '这个时段没有空位，或你已有同时段预约。可以换日期或时段。')))
    result['kinds']=[{'value':key,'label':t(request,label)} for key,label in VENUE_TYPES]
    return result


@never_cache
@login_required
@require_GET
def index(request):return render(request,'campus/task_assistant.html',{'external_ai_ready':companion_external.configured()})


@never_cache
@require_GET
def state(request):
    blocked=access(request)
    if blocked is not None:return blocked
    return JsonResponse(render_state(request,draft_for(request)))


@never_cache
@require_POST
def chat(request):
    blocked=access(request)
    if blocked is not None:return blocked
    try:
        data=payload(request)
        if set(data)-{'message','selection','reset','channel','history','weather_context','external_allowed'}:raise ValueError()
        if 'reset' in data:
            if data!={'reset':True}:raise ValueError()
            request.session.pop(SESSION_KEY,None)
            return JsonResponse(render_state(request,{}))
        if ('message' in data)==('selection' in data):raise ValueError()
        if 'message' in data:
            message=data['message']
            if not isinstance(message,str) or not 1<=len(message.strip())<=2000:raise ValueError()
            if not isinstance(data.get('external_allowed',False),bool):raise ValueError()
            channel=data.get('channel','auto')
            if channel not in ('auto','chat','task'):raise ValueError()
            history=validate_history(data.get('history',[]))
            weather_context=data.get('weather_context','')
            if not isinstance(weather_context,str) or len(weather_context)>2000:raise ValueError()
            spec=service_plans.candidate(message.strip()) if channel!='chat' else None
            if spec:
                plan,created=service_plans.create(request,message.strip(),spec)
                return JsonResponse({'phase':'plan','message':t(request,'已拆成办事计划，请先确认，再一步步完成。' if created else '你还有一份进行中的计划，先继续或结束它，再生成新计划。'),'plan':service_plans.serialize(request,plan)})
            if channel!='task':
                weather=companion_weather.lookup(message.strip(),history,context(request)['ui_language'],weather_context)
                if weather is not None:return JsonResponse(weather)
            if channel=='chat' or channel=='auto' and not task_request(message,draft_for(request)):
                language=context(request)['ui_language']
                external,note=companion_external.try_external(message.strip(),history,language,data.get('external_allowed',False))
                if external:return JsonResponse({'phase':'chat','mode':'external_ai','model':external['model'],'message':external['message'],'route_note':t(request,note)})
                try:content=answer(message.strip(),history,language)
                except ModelUnavailable:
                    return error(request,'本地 AI 暂时不可用或正在忙，请稍后重试。校园办事仍可使用下方选项。',503)
                return JsonResponse({'phase':'chat','mode':'local_ai','model':MODEL,'message':content,'route_note':t(request,note)})
            fields,mode=extract(message.strip(),timezone.localdate())
        else:
            fields=data['selection'];mode='rules'
            if isinstance(fields,dict) and set(fields)=={'weather'}:
                token=fields['weather']
                if not isinstance(token,str) or len(token)>2000:raise ValueError()
                return JsonResponse(companion_weather.chosen(token,context(request)['ui_language']))
            if not isinstance(fields,dict) or len(fields)!=1 or set(fields)-{'kind','building','day','slot'}:raise ValueError()
            if any(not isinstance(value,str) for value in fields.values()):raise ValueError()
            if 'kind' in fields and fields['kind'] not in dict(VENUE_TYPES):raise ValueError()
            if 'building' in fields and fields['building'] not in dict(STUDY_BUILDINGS):raise ValueError()
            if 'slot' in fields and fields['slot'] not in dict(TIME_SLOTS):raise ValueError()
    except (ValueError,TypeError,UnicodeDecodeError):return error(request,'请求不正确，请重新选择。')
    if fields.get('intent') in ('friends','help','health','services','manage'):
        request.session.pop(SESSION_KEY,None)
        return JsonResponse(navigation(request,fields['intent']))
    draft=draft_for(request)
    if draft.get('confirmed') or draft.get('plan_id') and set(fields)!={'building'}:draft={}
    draft.update(user=request.user.pk,key=str(uuid.uuid4()),expires=timezone.now().timestamp()+TTL)
    if fields.get('kind') in dict(VENUE_TYPES):
        if fields['kind']!=draft.get('kind'):draft.pop('building',None)
        draft['kind']=fields['kind']
    if fields.get('building') in dict(STUDY_BUILDINGS) and draft.get('kind')=='study':draft['building']=fields['building']
    note=None
    if fields.get('day'):
        try:
            chosen=date.fromisoformat(fields['day'])
            if not timezone.localdate()<=chosen<=timezone.localdate()+timedelta(days=14):raise ValueError()
            draft['day']=chosen.isoformat()
        except (ValueError,TypeError):
            draft.pop('day',None);draft.pop('slot',None);note='请选择今天至未来 14 天内的有效日期。'
    if fields.get('slot'):
        if fields['slot'] in dict(TIME_SLOTS):draft['slot']=fields['slot']
        else:draft.pop('slot',None);note='这个时间不对应开放时段，请从可选时段中选择。'
    if not fields:note='请核对下方信息，预约需要点击确认按钮提交。' if all(draft.get(key) for key in ('kind','day','slot')) else '我还没确定你的需求。可以说想预约什么场地，也可以点击下方选项。'
    request.session[SESSION_KEY]=draft
    return JsonResponse(render_state(request,draft,note,mode))


@never_cache
@require_POST
def confirm(request):
    blocked=access(request)
    if blocked is not None:return blocked
    try:
        data=payload(request)
        if set(data)!={'draft_key','venue_id'} or not isinstance(data['venue_id'],int) or isinstance(data['venue_id'],bool) or data['venue_id']<1:raise ValueError()
    except (ValueError,TypeError,UnicodeDecodeError):return error(request,'请求不正确，请重新选择。')
    draft=draft_for(request)
    if not draft or data['draft_key']!=draft.get('key'):return error(request,'这份预约草稿已过期或已更改，请重新查询。',409)
    if draft.get('confirmed'):
        record=VenueBooking.objects.filter(pk=draft['confirmed'],user=request.user,venue_id=data['venue_id']).first()
        if record:return JsonResponse(render_state(request,draft))
        return error(request,'这份预约草稿已过期或已更改，请重新查询。',409)
    form=BookingForm({'day':draft.get('day'),'slot':draft.get('slot'),'request_key':draft['key']})
    if not form.is_valid():return error(request,'预约信息不完整或时段已开始，请重新查询。',409)
    try:
        with transaction.atomic():
            plan=service_plans.lock_for_booking(request,draft)
            venue=Venue.objects.select_for_update().filter(pk=data['venue_id'],kind=draft.get('kind'),active=True).first()
            if venue and venue.kind=='study' and venue.building!=draft.get('building'):return error(request,'请先选择对应的自习楼栋。',409)
            if venue is None:return error(request,'该场地已暂停预约或与当前需求不符，请重新查询。',409)
            previous=VenueBooking.objects.filter(user=request.user,request_key=draft['key']).first()
            if previous:
                if previous.venue_id!=venue.pk:return error(request,'这份预约草稿已经使用，请重新查询。',409)
                record=previous
            else:record=waitlist.reserve(request.user,venue,**form.cleaned_data)
            service_plans.finish(plan,record)
    except ValueError:return error(request,'计划已更新，请刷新后继续。',409)
    except IntegrityError:return error(request,'空位刚被预约，或你已有同时段预约。请重新查询。',409)
    except OperationalError as issue:
        if 'locked' not in str(issue).lower():raise
        return error(request,'当前请求较多，请稍后重试。',503)
    draft['confirmed']=record.pk;request.session[SESSION_KEY]=draft
    return JsonResponse(render_state(request,draft))
