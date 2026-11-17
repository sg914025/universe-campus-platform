"""幂等站内通知与候补巡检。制作：UniVerse Team。"""
from datetime import timedelta
from django.db import transaction
from django.db.models import Q,Exists,OuterRef
from django.utils import timezone
from .models import BookingNotice,VenueBooking,VenueWaitlist
from .booking_forms import slot_start

def released_notice(item):
    return BookingNotice.objects.get_or_create(event_key=f'released:{item.pk}',defaults={'user_id':item.user_id,'kind':'seat_released','booking':item})
def offered_notice(row):
    return BookingNotice.objects.get_or_create(event_key=f'offered:{row.pk}',defaults={'user_id':row.user_id,'kind':'waitlist_offer','waitlist':row})
def remind_checkins(now=None):
    from .waitlist import locked_venue
    now=now or timezone.now();count=0
    ids=list(VenueBooking.objects.filter(status='reserved',checked_in_at__isnull=True,checkin_deadline__gt=now,checkin_deadline__lte=now+timedelta(minutes=25),day__lte=timezone.localdate(now+timedelta(minutes=10))).exclude(notices__kind='checkin_reminder').order_by('checkin_deadline').values_list('pk',flat=True)[:500])
    for pk in ids:
        with transaction.atomic():
            item=VenueBooking.objects.get(pk=pk);locked_venue(item.venue_id);item.refresh_from_db()
            if item.status!='reserved' or item.checked_in_at or not item.checkin_deadline or not now<item.checkin_deadline or slot_start(item.day,item.slot)>now+timedelta(minutes=10):continue
            _,created=BookingNotice.objects.get_or_create(event_key=f'reminder:{pk}',defaults={'user_id':item.user_id,'kind':'checkin_reminder','booking':item});count+=created
    return count

def advance_queues():
    from .waitlist import locked_venue,advance
    now=timezone.now()
    occupied=VenueBooking.objects.filter(venue_id=OuterRef('venue_id'),day=OuterRef('day'),slot=OuterRef('slot'),status='reserved')
    candidates=VenueWaitlist.objects.filter(Q(status='offered',offered_until__lte=now)|Q(status='waiting',day__lte=timezone.localdate())).annotate(occupied=Exists(occupied)).filter(Q(status='offered')|Q(occupied=False))
    keys=list(candidates.order_by().values_list('venue_id','day','slot').distinct()[:500])
    for venue_id,day,slot in keys:
        with transaction.atomic():advance(locked_venue(venue_id),day,slot)

def process_attendance():
    from .attendance import release_due
    released=release_due();remind_checkins();advance_queues();return released
