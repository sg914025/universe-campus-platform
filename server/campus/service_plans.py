"""Confirmed multi-service plans; no publication or booking without user action. Author: UniVerse Team."""
import json,re,uuid,unicodedata
from datetime import timedelta,date
from django.db import transaction,IntegrityError,OperationalError
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import CampusServicePlan,VenueBooking,TIME_SLOTS
from .task_intent import rules
from .booking_forms import can_book
from .ui_language import context,translate

LABELS={'friends':'找校园伙伴','help':'请求或提供帮助','health':'了解导诊服务','time':'选择活动时间','booking':'预约场地','share':'分享办事卡','navigate':'开启路线导航','checkin':'到场签到'}
ROUTES={'friends':'campus:friends','help':'campus:errands','health':'guide'}
def tr(request,text):return translate(text,context(request)['ui_language'])

def candidate(text):
    text=unicodedata.normalize('NFKC',text).lower()
    if any(x in text for x in ('取消','cancel','отмен','キャンセル','不想','不要',"don't want",'do not want','не хочу','したくない')):return None
    fields=rules(text,timezone.localdate())
    steps=[]
    for key,terms in {'friends':('认识同学','找伙伴','找球友','交友','meet students','make friends','find friends','знаком','друз','友達','仲間'),
        'help':('跑腿','取快递','取个快递','parcel','delivery','курьер','посыл','お使い','荷物'),
        'health':('导诊','就医','health guidance','clinic','врач','больниц','受診','病院')}.items():
        if any(term in text for term in terms):steps.append(key)
    kind=fields.get('kind','')
    if kind:steps+=['time','booking']
    if len([x for x in steps if x!='time'])<2:return None
    return {'steps':steps,'kind':kind,'weekend':any(x in text for x in ('周末','weekend','выходн','週末'))}

def friend_post_url(plan):
    return reverse('campus:post_create')+'?service_plan='+str(plan.pk)+'&revision='+str(plan.revision)

def post_plan(request):
    value=request.GET.get('service_plan')
    if not value:return None
    try:
        revision=uuid.UUID(request.GET.get('revision',''))
        plan=CampusServicePlan.objects.filter(pk=int(value),user=request.user,state='active',accepted=True,revision=revision).first()
    except (ValueError,TypeError,OverflowError):plan=None
    if plan is None or next((x for x in plan.steps if x not in plan.completed),None)!='friends':
        from django.http import Http404
        raise Http404('Plan changed or unavailable')
    return plan

def _save_progress(plan, step):
    if step not in plan.steps or step in plan.completed:
        return
    plan.completed = [*plan.completed, step]
    if all(key in plan.completed for key in plan.steps):
        plan.state = 'completed'
    plan.revision = uuid.uuid4()
    plan.save()


@transaction.atomic
def post_completed(request, plan, item):
    if plan is None or item.category != '交友' or item.author_id != request.user.pk:
        return False
    locked = CampusServicePlan.objects.select_for_update().filter(
        pk=plan.pk, user=request.user, state='active', revision=plan.revision).first()
    if not locked or current_step(locked) != 'friends':
        return False
    locked.linked_post = item
    _save_progress(locked, 'friends')
    return True


def current_step(plan):
    return next((key for key in plan.steps if key not in plan.completed), None)


def share_plan(request):
    """Called within the share transaction, before sending any message."""
    value = request.GET.get('service_plan')
    if not value:
        return None
    from django.http import Http404
    try:
        plan = CampusServicePlan.objects.select_for_update().filter(
            pk=int(value), user=request.user, state='active', accepted=True,
            revision=uuid.UUID(request.GET.get('revision', ''))).select_related('booking').first()
    except (ValueError, TypeError, OverflowError):
        plan = None
    if not plan or current_step(plan) != 'share' or not plan.booking or plan.booking.status != 'reserved':
        raise Http404('Plan changed or unavailable')
    return plan


def shared_completed(plan, message, booking):
    if plan is None:
        return False
    if booking.pk != plan.booking_id or booking.user_id != plan.user_id or message.sender_id != plan.user_id:
        raise ValueError('Plan resource mismatch')
    plan.shared_message = message
    _save_progress(plan, 'share')
    return True


@transaction.atomic
def checked_in(record):
    if not record.checked_in_at or record.status != 'reserved':
        return
    for plan in CampusServicePlan.objects.select_for_update().filter(
            booking=record, user_id=record.user_id, state='active', accepted=True):
        _save_progress(plan, 'checkin')


def booking_context(user, booking):
    if not user.is_authenticated:
        return None
    return CampusServicePlan.objects.filter(user=user, booking=booking).first()


def active(user):return CampusServicePlan.objects.filter(user=user,state='active').select_related('booking').first()

def serialize(request, plan):
    current = current_step(plan)
    today = timezone.localdate()
    days = [today + timedelta(days=i) for i in range(15)]
    spec = candidate(plan.source) or {}
    if spec.get('weekend'):
        days = [day for day in days if day.weekday() >= 5]
    receipt = None
    urls = {}
    blocked = False
    if plan.booking_id:
        record = plan.booking
        from .checkin_views import map_url
        share_url = reverse('campus:friend-hub') + '?booking=' + str(record.pk)
        if current == 'share' and plan.state == 'active':
            share_url += '&service_plan=' + str(plan.pk) + '&revision=' + str(plan.revision)
        urls = {'share': share_url + '#share-card', 'navigate': map_url(record),
                'checkin': reverse('campus:booking-checkin', args=[record.pk])}
        receipt = {'id': record.pk, 'status': tr(request, record.get_status_display()),
                   'active': record.status == 'reserved', 'url': reverse('campus:service-card', args=[record.pk]),
                   'name': record.venue.name, 'day': record.day.isoformat(), 'time': record.get_slot_display()}
        blocked = record.status != 'reserved' and plan.state == 'active'
    instructions = {
        'friends': '发布一条交友帖寻找伙伴，发布成功后自动继续计划。',
        'help': '进入跑腿服务核对需求，办妥后回来确认。',
        'health': '进入导诊整理需求，完成后回来继续。',
        'time': '请选择具体日期和时段，我不会替你默认决定。',
        'booking': '时间已确认，继续查空位并核对预约。',
        'share': '选择好友分享办事卡，发送成功后自动继续；也可暂不分享。',
        'navigate': '打开三维路线，到建筑入口后继续查看楼层和座位。开启路线不代表已经到场。',
        'checkin': '到场后扫码并确认签到，成功后自动完成计划。未到签到时间可稍后回来继续。',
    }
    instruction = ('这份计划已结束，可点击继续恢复进度。' if plan.state == 'cancelled' else
                   '计划已完成，你可以随时回顾进度。' if plan.state == 'completed' else
                   '请先确认这份计划，再逐项办理。' if not plan.accepted else
                   '关联预约已失效，请重新选择时间预约。' if blocked else instructions.get(current, '这份计划已结束。'))
    evidence = {}
    if plan.linked_post_id:
        evidence['friends'] = {'label': tr(request, '已发布交友帖'), 'url': reverse('campus:post_detail', args=[plan.linked_post_id])}
    if plan.shared_message_id:
        evidence['share'] = {'label': tr(request, '已发送办事卡')}
    if plan.navigation_started_at:
        evidence['navigate'] = {'label': tr(request, '已开启路线导航')}
    if plan.booking_id and plan.booking.checked_in_at:
        evidence['checkin'] = {'label': tr(request, '已签到')}
    return {'id': plan.pk, 'revision': str(plan.revision), 'source': plan.source,
            'accepted': plan.accepted, 'state': plan.state, 'workflow_version': plan.workflow_version,
            'current': current, 'kind': plan.kind, 'day': plan.day.isoformat() if plan.day else '', 'slot': plan.slot,
            'progress': len(plan.completed), 'total': len(plan.steps), 'receipt': receipt, 'blocked': blocked,
            'steps': [{'key': key, 'label': tr(request, '发布交友帖' if key == 'friends' and plan.workflow_version >= 2 else LABELS[key]),
                       'done': key in plan.completed, 'skipped': key in plan.skipped, 'evidence': evidence.get(key),
                       'url': urls.get(key) or (friend_post_url(plan) if key == 'friends' else reverse(ROUTES[key]) if key in ROUTES else '')}
                      for key in plan.steps],
            'days': [day.isoformat() for day in days], 'slots': [{'value': value, 'label': label} for value, label in TIME_SLOTS],
            'instruction': tr(request, instruction)}

def create(request,text,spec):
    plan=active(request.user)
    if plan:return plan,False
    try:
        with transaction.atomic():
            steps = list(spec['steps'])
            if 'booking' in steps: steps += ['share', 'navigate', 'checkin']
            plan=CampusServicePlan.objects.create(user=request.user,source=text,steps=steps,kind=spec['kind'],workflow_version=2)
    except IntegrityError:plan=active(request.user)
    return plan,True

def lock_for_booking(request,draft):
    if not draft.get('plan_id'):return None
    plan=CampusServicePlan.objects.select_for_update().filter(pk=draft['plan_id'],user=request.user,state='active',accepted=True,revision=draft.get('plan_revision')).first()
    if not plan or plan.day is None or plan.day.isoformat()!=draft.get('day') or plan.slot!=draft.get('slot') or plan.kind!=draft.get('kind') or next((x for x in plan.steps if x not in plan.completed),None)!='booking':
        raise ValueError('stale plan')
    return plan

def finish(plan, record):
    if plan is None:
        return
    plan.booking = record
    if plan.workflow_version >= 2:
        if record.checkin_deadline is None:
            from .booking_forms import slot_start
            record.checkin_deadline = slot_start(record.day, record.slot) + timedelta(minutes=15)
            record.save(update_fields=['checkin_deadline'])
        _save_progress(plan, 'booking')
    else:
        plan.completed = list(plan.steps)
        plan.state = 'completed'
        plan.revision = uuid.uuid4()
        plan.save()

@never_cache
@login_required
@require_http_methods(['GET','POST'])
def endpoint(request):
    if request.method=='GET':
        plan=active(request.user)
        if plan is None:plan=CampusServicePlan.objects.filter(user=request.user).select_related('booking').first()
        return JsonResponse({'plan':serialize(request,plan) if plan else None})
    try:
        if len(request.body)>10000:raise ValueError()
        data=json.loads(request.body)
        if not isinstance(data,dict) or set(data)-{'id','revision','action','day','slot'}:raise ValueError()
        if type(data.get('id')) is not int:raise ValueError()
        action=data.get('action')
        if action not in ('accept','complete','time','book','retime','cancel','resume','skip','navigated','rebook'):raise ValueError()
        if not isinstance(data.get('revision'),str):raise ValueError()
        revision=uuid.UUID(data['revision'])
        with transaction.atomic():
            plan=CampusServicePlan.objects.select_for_update().filter(pk=data['id'],user=request.user).first()
            if not plan:return JsonResponse({'error':tr(request,'找不到这份计划。')},status=404)
            old_state=plan.state
            allowed=plan.state=='active' or action=='resume' and plan.state=='cancelled'
            if plan.revision!=revision or not allowed:return JsonResponse({'error':tr(request,'计划已更新，请刷新后继续。')},status=409)
            current=next((x for x in plan.steps if x not in plan.completed),None)
            if action=='resume':
                if active(request.user):return JsonResponse({'error':tr(request,'已有另一份进行中的计划，请先结束它。')},status=409)
                plan.state='active'
                if plan.booking and plan.booking.checked_in_at and 'checkin' in plan.steps and 'checkin' not in plan.completed:
                    plan.completed=[*plan.completed,'checkin']
                    if all(key in plan.completed for key in plan.steps):plan.state='completed'
                if not plan.booking_id and plan.day and not can_book(plan.day,plan.slot):
                    plan.day=None;plan.slot='';plan.completed=[x for x in plan.completed if x!='time']
            elif action=='cancel':plan.state='cancelled'
            elif action=='accept':plan.accepted=True
            else:
                if not plan.accepted:raise ValueError()
                if action=='complete':
                    if current not in ROUTES or current == 'friends' and plan.workflow_version >= 2:raise ValueError()
                    plan.completed=[*plan.completed,current]
                    if len(plan.completed)==len(plan.steps):plan.state='completed'
                elif action=='skip':
                    if current not in ('share','navigate') or not plan.booking or plan.booking.status!='reserved':raise ValueError()
                    plan.skipped=[*plan.skipped,current];plan.completed=[*plan.completed,current]
                    if all(key in plan.completed for key in plan.steps):plan.state='completed'
                elif action=='navigated':
                    if current!='navigate' or not plan.booking or plan.booking.status!='reserved':raise ValueError()
                    plan.navigation_started_at=timezone.now();plan.completed=[*plan.completed,'navigate']
                    if all(key in plan.completed for key in plan.steps):plan.state='completed'
                elif action=='rebook':
                    if not plan.booking or plan.booking.status=='reserved':raise ValueError()
                    plan.booking=None;plan.shared_message=None;plan.navigation_started_at=None
                    plan.day=None;plan.slot=''
                    plan.completed=[key for key in plan.completed if key not in ('time','booking','share','navigate','checkin')]
                    plan.skipped=[]
                elif action=='retime':
                    if current!='booking':raise ValueError()
                    plan.day=None;plan.slot='';plan.completed=[x for x in plan.completed if x!='time']
                elif action=='time':
                    if current!='time':raise ValueError()
                    day=date.fromisoformat(data.get('day',''));slot=data.get('slot')
                    if not timezone.localdate()<=day<=timezone.localdate()+timedelta(days=14) or slot not in dict(TIME_SLOTS) or not can_book(day,slot):raise ValueError()
                    spec=candidate(plan.source) or {}
                    if spec.get('weekend') and day.weekday()<5:raise ValueError()
                    plan.day=day;plan.slot=slot;plan.completed=[*plan.completed,'time']
                elif action=='book':
                    if current!='booking' or not can_book(plan.day,plan.slot):raise ValueError()
            # Conditional revision prevents stale tabs from overwriting newer progress on SQLite too.
            new_revision=uuid.uuid4()
            updated=CampusServicePlan.objects.filter(pk=plan.pk,revision=revision,state=old_state).update(accepted=plan.accepted,completed=plan.completed,day=plan.day,slot=plan.slot,state=plan.state,revision=new_revision,updated_at=timezone.now(),booking=plan.booking,shared_message=plan.shared_message,navigation_started_at=plan.navigation_started_at,skipped=plan.skipped)
            if updated!=1:return JsonResponse({'error':tr(request,'计划已更新，请刷新后继续。')},status=409)
            plan.revision=new_revision
            result={'plan':serialize(request,plan)}
            if action in ('accept','resume') and plan.accepted and current_step(plan)=='friends':result['next_url']=friend_post_url(plan)
            if action=='book':
                from .task_assistant import SESSION_KEY,TTL,render_state
                draft={'user':request.user.pk,'key':str(uuid.uuid4()),'expires':timezone.now().timestamp()+TTL,
                    'kind':plan.kind,'day':plan.day.isoformat(),'slot':plan.slot,'plan_id':plan.pk,'plan_revision':str(plan.revision)}
                request.session[SESSION_KEY]=draft;result['assistant']=render_state(request,draft)
            return JsonResponse(result)
    except IntegrityError:return JsonResponse({'error':tr(request,'已有另一份进行中的计划，请先结束它。')},status=409)
    except OperationalError as issue:
        if 'locked' not in str(issue).lower():raise
        return JsonResponse({'error':tr(request,'当前请求较多，请稍后重试。')},status=503)
    except (ValueError,TypeError,UnicodeDecodeError):return JsonResponse({'error':tr(request,'请按当前步骤确认，并选择有效的日期和时段。')},status=400)
