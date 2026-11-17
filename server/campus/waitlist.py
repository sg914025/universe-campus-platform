"""First-in-first-out offers, held for 15 minutes. No automatic bookings."""
import uuid
from datetime import timedelta
from django.db import IntegrityError,transaction
from django.db.models import F
from django.utils import timezone
from .models import Venue,VenueBooking,VenueWaitlist,TIME_SLOTS
from .booking_forms import can_book,slot_start

class BookingUnavailable(IntegrityError):pass

def locked_venue(pk):
    venue=Venue.objects.select_for_update().get(pk=pk)
    # Also serialize writers on SQLite, where SELECT FOR UPDATE is a no-op.
    Venue.objects.filter(pk=pk).update(active=F('active'))
    return venue

def advance(venue,day,slot):
    """Caller holds the venue write lock inside an atomic transaction."""
    rows=VenueWaitlist.objects.filter(venue=venue,day=day,slot=slot)
    now=timezone.now()
    rows.filter(status='offered',offered_until__lte=now).update(status='expired')
    from .attendance import bookable,slot_end
    occupied=VenueBooking.objects.filter(venue=venue,day=day,slot=slot,status='reserved').exists()
    if not venue.active or now>=slot_end(day,slot)-timedelta(minutes=15):
        rows.filter(status__in=['waiting','offered']).update(status='expired');return None
    # Keep queued users waiting while the current booking can still check in.
    if occupied:return None
    if not bookable(venue,day,slot):
        rows.filter(status__in=['waiting','offered']).update(status='expired');return None
    for row in rows.filter(status__in=['waiting','offered']).select_related('user').order_by('created_at','pk'):
        if not row.user.is_active or VenueBooking.objects.filter(user=row.user,day=day,slot=slot,status='reserved').exists():
            row.status='ineligible';row.save(update_fields=['status']);continue
        if row.status=='waiting':
            row.status='offered';cutoff=slot_start(day,slot) if slot_start(day,slot)>now else slot_end(day,slot)-timedelta(minutes=15);row.offered_until=min(now+timedelta(minutes=15),cutoff)
            row.save(update_fields=['status','offered_until'])
        from .booking_notices import offered_notice
        offered_notice(row)
        return row
    return None

@transaction.atomic
def reserve(user,venue,day,slot,request_key):
    previous=VenueBooking.objects.filter(user=user,request_key=request_key).first()
    if previous:
        if previous.venue_id!=venue.pk or previous.day!=day or previous.slot!=slot:raise BookingUnavailable('request mismatch')
        return previous
    venue=locked_venue(venue.pk)
    from .attendance import bookable
    if not venue.active or slot not in dict(TIME_SLOTS) or not bookable(venue,day,slot):raise BookingUnavailable('not available')
    offer=advance(venue,day,slot)
    if offer and offer.user_id!=user.pk:raise BookingUnavailable('held for waitlist')
    deadline=None
    if venue.kind=='study':deadline=max(slot_start(day,slot),timezone.now())+timedelta(minutes=15)
    booking=VenueBooking.objects.create(user=user,venue=venue,day=day,slot=slot,request_key=request_key,checkin_deadline=deadline)
    if offer:
        offer.status='claimed';offer.booking=booking;offer.claimed_at=timezone.now();offer.save(update_fields=['status','booking','claimed_at'])
    return booking

@transaction.atomic
def join(user,venue,day,slot):
    venue=locked_venue(venue.pk)
    if not venue.active or slot not in dict(TIME_SLOTS) or not can_book(day,slot):raise BookingUnavailable('not available')
    if VenueBooking.objects.filter(user=user,day=day,slot=slot,status='reserved').exists():raise BookingUnavailable('personal conflict')
    previous=VenueWaitlist.objects.filter(user=user,venue=venue,day=day,slot=slot,status__in=['waiting','offered']).first()
    if previous:return previous
    occupied=VenueBooking.objects.filter(venue=venue,day=day,slot=slot,status='reserved').exists()
    if not occupied and not VenueWaitlist.objects.filter(venue=venue,day=day,slot=slot,status__in=['waiting','offered']).exists():raise BookingUnavailable('book directly')
    row=VenueWaitlist.objects.create(user=user,venue=venue,day=day,slot=slot)
    advance(venue,day,slot);row.refresh_from_db();return row

@transaction.atomic
def cancel_booking(user,pk):
    item=VenueBooking.objects.get(pk=pk,user=user)
    venue=locked_venue(item.venue_id)
    if item.status=='reserved' and slot_start(item.day,item.slot)>timezone.now():
        VenueBooking.objects.filter(pk=pk,status='reserved').update(status='cancelled',cancelled_at=timezone.now())
        advance(venue,item.day,item.slot)
        return True
    return False

@transaction.atomic
def refresh(row):
    return advance(locked_venue(row.venue_id),row.day,row.slot)

@transaction.atomic
def leave(row):
    venue=locked_venue(row.venue_id)
    VenueWaitlist.objects.filter(pk=row.pk,status__in=['waiting','offered']).update(status='cancelled')
    advance(venue,row.day,row.slot)

@transaction.atomic
def claim(row,user):
    row.refresh_from_db()
    if row.status=='claimed' and row.booking_id and row.user_id==user.pk:return row.booking
    venue=locked_venue(row.venue_id)
    offered=advance(venue,row.day,row.slot)
    if not offered or offered.pk!=row.pk or offered.user_id!=user.pk:raise BookingUnavailable('offer expired')
    return reserve(user,venue,row.day,row.slot,uuid.uuid5(uuid.NAMESPACE_URL,'universe-waitlist-'+str(row.pk)))
