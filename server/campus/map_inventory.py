"""Reservation inventory for the campus interior. Never expose occupants."""
from datetime import date,timedelta
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import Venue,VenueBooking,VenueWaitlist,TIME_SLOTS,VENUE_TYPES
from .attendance import bookable
from .booking_forms import can_book

AREAS=('A','B','C','library','gym','outdoor')

@never_cache
@require_GET
def inventory(request):
    today=timezone.localdate();last=today+timedelta(days=14)
    area=request.GET.get('area','')
    if area not in AREAS:return JsonResponse({'error':'Invalid building'},status=400)
    day=today
    if not request.GET.get('day') and not any(can_book(day,code) for code,_ in TIME_SLOTS):day+=timedelta(days=1)
    try:
        if request.GET.get('day'):day=date.fromisoformat(request.GET['day'])
        if not today<=day<=last:raise ValueError()
        slot=request.GET.get('slot') or next((code for code,_ in TIME_SLOTS if can_book(day,code)),TIME_SLOTS[0][0])
        if slot not in dict(TIME_SLOTS):raise ValueError()
    except (ValueError,TypeError):return JsonResponse({'error':'Invalid day or slot'},status=400)
    venues=Venue.objects.filter(map_area=area) if area in ('gym','outdoor') else Venue.objects.filter(kind='study',building=area)
    venues=list(venues.order_by('floor','kind','name','pk'))
    ids=[v.pk for v in venues]
    booked=set(VenueBooking.objects.filter(venue_id__in=ids,day=day,slot=slot,status='reserved').values_list('venue_id',flat=True))
    held=set(VenueWaitlist.objects.filter(venue_id__in=ids,day=day,slot=slot,status='offered',offered_until__gt=timezone.now()).values_list('venue_id',flat=True))
    conflict=request.user.is_authenticated and VenueBooking.objects.filter(user=request.user,day=day,slot=slot,status='reserved').exists()
    own=set(VenueBooking.objects.filter(user=request.user,venue_id__in=ids,day=day,slot=slot,status='reserved').values_list('venue_id',flat=True)) if request.user.is_authenticated else set()
    resources=[]
    for v in venues:
        status='closed' if not v.active else 'booked' if v.pk in booked else 'held' if v.pk in held else 'past' if not bookable(v,day,slot) else 'conflict' if conflict else 'free'
        resources.append({'id':v.pk,'name':v.name,'kind':v.kind,'kind_label':dict(VENUE_TYPES)[v.kind],'floor':v.floor,
            'state':status,'mine':v.pk in own,'demo':v.is_demo,
            'url':reverse('campus:booking-venue',args=[v.pk])+f'?day={day.isoformat()}&slot={slot}'})
    return JsonResponse({'area':area,'day':day.isoformat(),'slot':slot,'today':today.isoformat(),'last_day':last.isoformat(),
        'slots':[{'code':code,'label':label} for code,label in TIME_SLOTS],
        'floors':sorted({v.floor for v in venues}),'resources':resources,'updated':timezone.localtime().strftime('%H:%M:%S'),
        'counts':{status:sum(v['state']==status for v in resources) for status in ('free','booked','held','closed','past','conflict')}})
