"""Local room reservations. All dates, capacity and permissions are server checked."""
import json
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from .models import RoomAppointment
from .rooms import ROOMS

ZONE = ZoneInfo('Asia/Shanghai')
CAPACITY = 5
ROOM_MAP = {row[0]: row for row in ROOMS}


def local_now():
    return timezone.localtime(timezone.now(), ZONE)


def allowed_date(value, now):
    try:
        selected = date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError('请选择正确的预约日期。')
    if not now.date() <= selected <= now.date() + timedelta(days=3):
        raise ValueError('最多提前3天预约，不能预约过去的日期。')
    return selected


def starts_for(room, day, now):
    if room not in ('room1', 'room2', 'room3'):
        return []
    hours = (8, 9, 10, 11, 14, 15, 16)
    return [start for hour in hours if (start := datetime.combine(day, time(hour), ZONE)) > now]


def serialize(record):
    start = timezone.localtime(record.starts_at, ZONE)
    end = timezone.localtime(record.ends_at, ZONE)
    return {'id': record.pk, 'code': record.code, 'room': record.room,
        'name': ROOM_MAP[record.room][1], 'date': start.date().isoformat(),
        'time': start.strftime('%H:%M') + '–' + ('24:00' if end.date() > start.date() else end.strftime('%H:%M')),
        'number': record.number, 'status': record.status,
        'can_cancel': record.status == 'confirmed' and record.starts_at > timezone.now()}


def schedule(day, now):
    beginning = datetime.combine(day, time(), ZONE)
    used = {(row['room'], row['starts_at']): row['count'] for row in
        RoomAppointment.objects.filter(status='confirmed', starts_at__gte=beginning, starts_at__lt=beginning + timedelta(days=1))
        .values('room', 'starts_at').annotate(count=Count('id'))}
    rooms = []
    for key, name, category, desc, icon in ROOMS:
        slots = []
        for start in starts_for(key, day, now):
            end = start + timedelta(hours=1)
            slots.append({'start': start.isoformat(), 'label': start.strftime('%H:%M') + '–' + ('24:00' if end.date() > start.date() else end.strftime('%H:%M')),
                'remaining': max(0, CAPACITY-used.get((key, start), 0)), 'capacity': CAPACITY})
        rooms.append({'id': key, 'name': name, 'category': category, 'desc': desc, 'icon': icon,
            'available': key.startswith('emergency') or any(s['remaining'] > 0 for s in slots),
            'requires_booking': key in ('room1', 'room2', 'room3'), 'slots': slots})
    return {'date': day.isoformat(), 'today': now.date().isoformat(), 'max_date': (now.date()+timedelta(days=3)).isoformat(),
        'dates': [(now.date()+timedelta(days=i)).isoformat() for i in range(4)],
        'server_time': now.isoformat(), 'after_hours': now.hour >= 17 and day == now.date(), 'rooms': rooms}


def auth_error(request):
    from .views import access_error
    return access_error(request)


@never_cache
@require_GET
def availability(request):
    error = auth_error(request)
    if error is not None:
        return error
    now = local_now()
    try:
        day = allowed_date(request.GET.get('date', now.date().isoformat()), now)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse(schedule(day, now))


@never_cache
@require_GET
def mine(request):
    error = auth_error(request)
    if error is not None:
        return error
    records = RoomAppointment.objects.filter(user=request.user).order_by('-created_at')[:50]
    return JsonResponse({'appointments': [serialize(r) for r in records]})


@never_cache
@require_POST
def reserve(request):
    error = auth_error(request)
    if error is not None:
        return error
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError()
        room = data.get('room')
        key = uuid.UUID(data.get('request_key', ''))
        start = parse_datetime(data.get('start', ''))
        if not isinstance(room, str) or room not in ROOM_MAP or start is None or timezone.is_naive(start):
            raise ValueError()
        start = timezone.localtime(start, ZONE)
    except (ValueError, TypeError, AttributeError, UnicodeDecodeError, OverflowError):
        return JsonResponse({'error': '预约信息不正确，请重新选择。'}, status=400)
    existing = RoomAppointment.objects.filter(user=request.user, request_key=key).first()
    if existing:
        if existing.room == room and existing.starts_at == start and existing.status == 'confirmed':
            return JsonResponse({'appointment': serialize(existing)})
        return JsonResponse({'error': '预约信息已变化，请重新选择时段。'}, status=409)
    now = local_now()
    try:
        day = allowed_date(start.date().isoformat(), now)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    if start not in starts_for(room, day, now):
        if room.startswith('emergency'):
            return JsonResponse({'error': '急诊无需预约，请直接前往诊室等待大厅。'}, status=400)
        return JsonResponse({'error': '该时段不可预约，17:00后仅开放急诊。'}, status=400)
    if RoomAppointment.objects.filter(user=request.user, starts_at=start, status='confirmed').exists():
        return JsonResponse({'error': '你已预约同一时间段，请先取消原预约。'}, status=409)
    # Database constraints are the final guard against two simultaneous requests
    # claiming the same number or the same patient's time.
    for number in range(1, CAPACITY+1):
        try:
            with transaction.atomic():
                record = RoomAppointment.objects.create(user=request.user, room=room, starts_at=start,
                    ends_at=start+timedelta(hours=1), number=number, request_key=key)
            return JsonResponse({'appointment': serialize(record)}, status=201)
        except IntegrityError:
            duplicate = RoomAppointment.objects.filter(user=request.user, request_key=key).first()
            if duplicate:
                if duplicate.room == room and duplicate.starts_at == start and duplicate.status == 'confirmed':
                    return JsonResponse({'appointment': serialize(duplicate)})
                return JsonResponse({'error': '预约信息已变化，请重新选择时段。'}, status=409)
            if RoomAppointment.objects.filter(user=request.user, starts_at=start, status='confirmed').exists():
                return JsonResponse({'error': '你已预约同一时间段，请先取消原预约。'}, status=409)
        except OperationalError:
            return JsonResponse({'error': '预约人数较多，请刷新后重试。'}, status=409)
    return JsonResponse({'error': '该时段号源已满，请选择其他时段。'}, status=409)


@never_cache
@require_POST
def cancel(request, pk):
    error = auth_error(request)
    if error is not None:
        return error
    record = get_object_or_404(RoomAppointment, pk=pk, user=request.user)
    if record.status == 'cancelled':
        return JsonResponse({'appointment': serialize(record)})
    now = timezone.now()
    changed = RoomAppointment.objects.filter(pk=record.pk, user=request.user, status='confirmed', starts_at__gt=now).update(status='cancelled', cancelled_at=now)
    if not changed:
        record.refresh_from_db()
        if record.status == 'cancelled':
            return JsonResponse({'appointment': serialize(record)})
        return JsonResponse({'error': '该预约已经开始，无法取消。'}, status=409)
    record.refresh_from_db()
    return JsonResponse({'appointment': serialize(record)})
