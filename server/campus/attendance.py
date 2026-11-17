"""预约到场规则。制作：UniVerse Team。仅核验扫码账户，不作为物理定位证明。"""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import VenueBooking
from .booking_forms import slot_start

def slot_end(day,slot):return slot_start(day,slot)+timedelta(hours=2)
def bookable(venue,day,slot):
    from .booking_forms import can_book
    if can_book(day,slot):return True
    now=timezone.now()
    return venue.kind=='study' and slot_start(day,slot)<=now<slot_end(day,slot)-timedelta(minutes=15) and VenueBooking.objects.filter(venue=venue,day=day,slot=slot,status__in=['no_show','released']).exists()

def release_due(now=None):
    from .waitlist import locked_venue,advance
    now=now or timezone.now();count=0
    ids=list(VenueBooking.objects.filter(status='reserved',checked_in_at__isnull=True,checkin_deadline__lte=now).values_list('pk',flat=True)[:500])
    for pk in ids:
        with transaction.atomic():
            item=VenueBooking.objects.get(pk=pk);venue=locked_venue(item.venue_id)
            changed=mark_no_show(pk,now)
            if changed:advance(venue,item.day,item.slot);count+=changed
    return count

@transaction.atomic
def check_in(user,pk):
    from .waitlist import locked_venue
    item=VenueBooking.objects.get(pk=pk,user=user);locked_venue(item.venue_id);item.refresh_from_db();now=timezone.now()
    if item.status!='reserved' or not item.checkin_deadline:return item,'unavailable'
    if item.checked_in_at:
        from .service_plans import checked_in
        checked_in(item)
        return item,'already'
    if now>=item.checkin_deadline:
        mark_no_show(pk,now)
        item.refresh_from_db();return item,'expired'
    if now<slot_start(item.day,item.slot)-timedelta(minutes=15):return item,'early'
    item.checked_in_at=now;item.save(update_fields=['checked_in_at'])
    from .service_plans import checked_in
    checked_in(item)
    return item,'ok'


def start_worker():
    import threading,time,logging
    from django.db import close_old_connections,OperationalError,ProgrammingError
    def run():
        while True:
            time.sleep(30);close_old_connections()
            try:
                from .booking_notices import process_attendance
                process_attendance()
            except (OperationalError,ProgrammingError):logging.getLogger(__name__).warning('Seat expiry deferred: database unavailable')
    threading.Thread(target=run,name='seat-expiry',daemon=True).start()


def mark_no_show(pk,now):
    from .models import StaffAuditEvent
    changed=VenueBooking.objects.filter(pk=pk,status='reserved',checked_in_at__isnull=True,checkin_deadline__lte=now).update(status='no_show',cancelled_at=now,released_at=now,release_reason='超时未签到')
    if changed:StaffAuditEvent.objects.create(actor_name='系统自动',module='booking',action='超时未签到自动释放',target=f'campus.venuebooking:{pk}',changed_fields=['status'],before_state={'status':'reserved'},after_state={'status':'no_show'})
    if changed:
        from .booking_notices import released_notice
        released_notice(VenueBooking.objects.get(pk=pk))
    return changed

@transaction.atomic
def manual_release(actor,pk,reason,confirm_checked_in=False):
    from .waitlist import locked_venue,advance
    from .audit import record_event
    item=VenueBooking.objects.get(pk=pk);venue=locked_venue(item.venue_id);item.refresh_from_db();now=timezone.now()
    if item.venue.kind!='study' or item.status!='reserved' or slot_end(item.day,item.slot)<=now:return False
    if item.checked_in_at and not confirm_checked_in:raise ValueError('该预约已签到，请确认后再释放。')
    reason=reason.strip()
    if not reason or len(reason)>200:raise ValueError('请填写200字以内的释放原因。')
    item.status='released';item.cancelled_at=now;item.released_at=now;item.released_by=actor;item.release_reason=reason;item.save(update_fields=['status','cancelled_at','released_at','released_by','release_reason'])
    record_event(actor,'booking','手动释放座位',item,['status'],{'status':'reserved'},{'status':'released'})
    from .booking_notices import released_notice
    released_notice(item)
    advance(venue,item.day,item.slot);return True
