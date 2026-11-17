from datetime import timedelta
from io import BytesIO
from urllib.parse import urlencode
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import HttpResponse,HttpResponseBadRequest
from django.shortcuts import get_object_or_404,render,redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET,require_http_methods
from .models import VenueBooking
from .booking_forms import slot_start
from .attendance import check_in,release_due
# 制作：UniVerse Team。二维码只核验账号，不验证物理位置。
def token_for(item):return signing.dumps({'booking':item.pk,'user':item.user_id},salt='universe-seat-checkin',compress=True)
def map_url(item):
    venue=item.venue;area=venue.building if venue.kind=='study' else venue.map_area
    return reverse('campus:campus-map')+'?'+urlencode({'area':area,'floor':venue.floor,'seat':venue.pk,'day':item.day.isoformat(),'slot':item.slot,'navigate':'1','booking':item.pk})
@never_cache
@login_required
@require_http_methods(['GET','POST'])
def checkin(request,pk):
    from .service_plans import booking_context
    release_due();item=get_object_or_404(VenueBooking.objects.select_related('venue'),pk=pk,user=request.user);result=''
    if request.method=='POST':
        try:
            if signing.loads(request.POST.get('token',''),salt='universe-seat-checkin')!={'booking':item.pk,'user':request.user.pk}:raise signing.BadSignature()
        except signing.BadSignature:return HttpResponseBadRequest('Invalid QR token')
        item,result=check_in(request.user,pk)
        if result in ('ok','already'):return redirect('campus:booking-checkin',pk=pk)
    return render(request,'campus/booking/checkin.html',{'flow_plan':booking_context(request.user,item),'item':item,'token':token_for(item),'result':result,'nav_url':map_url(item),'can_checkin':item.status=='reserved' and not item.checked_in_at and item.checkin_deadline and slot_start(item.day,item.slot)-timedelta(minutes=15)<=timezone.now()<item.checkin_deadline})
@never_cache
@login_required
@require_GET
def qr(request,pk):
    import qrcode
    item=get_object_or_404(VenueBooking,pk=pk,user=request.user);url=request.build_absolute_uri(reverse('campus:booking-checkin',args=[pk]))+'?'+urlencode({'scan':token_for(item)})
    output=BytesIO();qrcode.make(url).save(output,format='PNG');response=HttpResponse(output.getvalue(),content_type='image/png');response['Cache-Control']='private, no-store';return response
@never_cache
@login_required
@require_GET
def navigate(request,pk):return redirect(map_url(get_object_or_404(VenueBooking.objects.select_related('venue'),pk=pk,user=request.user)))
