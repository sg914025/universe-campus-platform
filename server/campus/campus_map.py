from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import Venue,VenueBooking
from .ui_language import context,translate

@never_cache
@require_GET
def index(request):
    language=context(request)['ui_language']
    kinds={kind:Venue.objects.filter(kind=kind,active=True).count() for kind in ('study','badminton','basketball','table_tennis','football')}
    data={'inventory':reverse('campus:map-inventory'),'counts':kinds,'updated':timezone.localtime().strftime('%Y-%m-%d %H:%M'),'urls':{
        'study':reverse('campus:booking')+'?kind=study','sport':reverse('campus:booking')+'?kind=badminton',
        'life':reverse('campus:errands'),'health':reverse('guide'),'social':reverse('campus:friends'),
        'assistant':reverse('task-assistant')}}
    flow_plan=None
    if request.user.is_authenticated and request.GET.get('booking','').isdecimal():
        from .service_plans import booking_context,current_step
        item=VenueBooking.objects.filter(pk=request.GET['booking'],user=request.user).first()
        if item and request.GET.get('seat')==str(item.venue_id) and request.GET.get('area')==(item.venue.building if item.venue.kind=='study' else item.venue.map_area):
            flow_plan=booking_context(request.user,item)
            if flow_plan and flow_plan.state=='active' and flow_plan.accepted and current_step(flow_plan)=='navigate' and item.status=='reserved':
                data['plan_navigation']={'id':flow_plan.pk,'revision':str(flow_plan.revision),'action':'navigated'}
    return render(request,'campus/campus_map.html',{'map_data':data,'flow_plan':flow_plan})
