from datetime import date
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import VenueBooking
from .ui_language import context,translate

@never_cache
@login_required
@require_GET
def agenda(request):
    today=timezone.localdate()
    try:
        month=request.GET.get('month',today.strftime('%Y-%m'))
        if len(month)!=7 or month[4]!='-':raise ValueError()
        first=date(int(month[:4]),int(month[5:]),1)
        if not 2000<=first.year<=2100:raise ValueError()
        end=date(first.year+1,1,1) if first.month==12 else date(first.year,first.month+1,1)
    except (ValueError,TypeError):return JsonResponse({'error':'Invalid month'},status=400)
    lang=context(request)['ui_language']
    own=VenueBooking.objects.filter(user=request.user).select_related('venue')
    def serialize(item):
        return {'id':item.pk,'name':item.venue.name,'day':item.day.isoformat(),
            'time':item.get_slot_display(),'location':item.venue.location,
            'status':translate(item.get_status_display(),lang),'active':item.status=='reserved',
            'url':reverse('campus:service-card',args=[item.pk]),
            'calendar':reverse('campus:service-calendar',args=[item.pk])}
    from .service_plans import active,serialize as serialize_plan
    plan=active(request.user)
    response=JsonResponse({'plan':serialize_plan(request,plan) if plan else None,'today':today.isoformat(),'month':month,'language':lang,
        'events':[serialize(x) for x in own.filter(day__gte=first,day__lt=end).order_by('day','slot','pk')],
        'cards':[serialize(x) for x in own.filter(status='reserved',day__gte=today).order_by('day','slot','pk')[:4]]})
    response['Cache-Control']='private, no-store'
    return response
