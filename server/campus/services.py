"""Personal service overview; reuse each module's ownership and read states."""
from datetime import datetime, time, timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from 个人信息.social import unread_for
from 帖子.models import post
from 跑腿.models import task, question
from triage.models import Consultation, RoomAppointment
from triage.rooms import ROOMS
from .models import VenueBooking,BookingNotice


def unread_sources(user):
    return {
        'forum': unread_for(user).filter(is_hidden=False),
        'health': Consultation.objects.filter(user=user, status='replied', reply_read=False).exclude(doctor_reply=''),
        'errands': question.objects.filter(user=user, reply_unread=True),
        'booking': BookingNotice.objects.filter(user=user,is_read=False),
    }


def unread_count(user):
    return sum(query.count() for query in unread_sources(user).values()) if user.is_authenticated else 0


def personal_services(user):
    now=timezone.now()
    errands=task.objects.filter(Q(owner=user)|Q(runner=user))
    active=errands.filter(status__in=['open','accepted','delivered'])
    # An ongoing slot remains visible until it ends, rather than vanishing at its start.
    bookings=VenueBooking.objects.filter(user=user,status='reserved',day__gte=timezone.localdate()).select_related('venue').order_by('day','slot','pk')
    upcoming=[]
    for booking in bookings:
        end=timezone.make_aware(datetime.combine(booking.day,time(int(booking.slot),0)))+timedelta(hours=2)
        if end>now:upcoming.append(booking)
    rooms=RoomAppointment.objects.filter(user=user,status='confirmed',ends_at__gt=now).order_by('starts_at','pk')
    room_names={row[0]:row[1] for row in ROOMS}
    for room in rooms:room.room_label=room_names.get(room.room,room.room)
    consultations=Consultation.objects.filter(user=user)
    sources=unread_sources(user)
    notices=[]
    for row in sources['forum'].select_related('sender').order_by('-created_at','-pk')[:20]:
        notices.append({'kind':'forum','pk':row.pk,'title':'收到一条校园私信','module':'校园广场','at':row.created_at,'url':reverse('campus:chat',args=[row.sender_id])})
    for row in sources['health'].order_by('-replied_at','-pk')[:20]:
        notices.append({'kind':'health','pk':row.pk,'title':'医生已回复你的咨询','module':'AI 导诊','at':row.replied_at or row.created_at,'url':reverse('guide')+'?page=inbox'})
    for row in sources['errands'].order_by('-updated_at','-pk')[:20]:
        notices.append({'kind':'errands','pk':row.pk,'title':'跑腿咨询收到管理员回复','module':'校园跑腿','at':row.updated_at,'url':reverse('campus:errand_question',args=[row.pk])})
    for row in sources['booking'].select_related('booking','waitlist').order_by('-created_at','-pk')[:20]:
        title={'checkin_reminder':'赴约签到提醒','seat_released':'你的座位预约已释放','waitlist_offer':'候补空位已为你保留，请及时确认'}[row.kind]
        if row.kind=='checkin_reminder' and row.booking and (row.booking.status!='reserved' or row.booking.checked_in_at):title='预约状态已更新，请查看记录'
        if row.kind=='waitlist_offer' and row.waitlist and (row.waitlist.status!='offered' or not row.waitlist.offered_until or row.waitlist.offered_until<=now):title='候补名额状态已更新，请查看记录'
        url=reverse('campus:waitlist') if row.kind=='waitlist_offer' else reverse('campus:booking-checkin',args=[row.booking_id]) if row.booking_id else reverse('campus:booking-mine')
        notices.append({'kind':'booking','pk':row.pk,'title':title,'module':'场地预约','at':row.created_at,'url':url,'deadline':row.waitlist.offered_until if row.kind=='waitlist_offer' and row.waitlist else row.booking.checkin_deadline if row.kind=='checkin_reminder' and row.booking else None})
    notices.sort(key=lambda row:(row['at'],row['pk']),reverse=True)
    return {
        'unread_total':sum(query.count() for query in sources.values()),
        'notices':notices[:20],
        'forum_unread':sources['forum'].count(),
        'active_errands':active.count(),
        'awaiting_confirmation':active.filter(owner=user,status='delivered').count(),
        'awaiting_delivery':active.filter(runner=user,status='accepted').count(),
        'upcoming_count':len(upcoming)+len(rooms),
        'pending_consultations':consultations.filter(status='pending').count(),
        'errands':errands.order_by('-created_at','-pk')[:5],
        'bookings':upcoming[:5], 'appointments':list(rooms[:5]),
        'consultations':consultations.order_by('-created_at','-pk')[:5],
        'posts':post.objects.filter(author=user,is_hidden=False).order_by('-created_at','-pk')[:5],
    }


@never_cache
@login_required
@require_GET
def index(request):
    return render(request,'campus/services.html',personal_services(request.user))


@never_cache
@login_required
@require_GET
def count(request):
    return JsonResponse({'unread':unread_count(request.user)})


@never_cache
@login_required
@require_POST
def read(request):
    sources=unread_sources(request.user)
    kind=request.POST.get('kind')
    raw=request.POST.get('id','')
    if kind not in sources or not raw.isdecimal() or len(raw)>18:
        return HttpResponseBadRequest('Invalid notification')
    # Ownership is checked again on every mutation; never trust the submitted ID.
    query=sources[kind]
    row=get_object_or_404(query,pk=int(raw))
    field={'forum':'is_read','health':'reply_read','errands':'reply_unread','booking':'is_read'}[kind]
    values={field:kind!='errands'}
    if kind=='booking':values['read_at']=timezone.now()
    query.filter(pk=row.pk).update(**values)
    return redirect('my-services')
