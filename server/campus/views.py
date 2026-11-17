from django.shortcuts import render,redirect
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from accounts.models import Profile
from triage.models import DoctorProfile
from accounts.regions import PROVINCES
from .heritage import OUTFITS

@never_cache
@require_GET
def home(request):
    profile=None
    is_doctor=False
    if request.user.is_authenticated:
        is_doctor=DoctorProfile.objects.filter(user=request.user,active=True).exists()
        profile=Profile.objects.filter(user=request.user).first()
        if not is_doctor and not request.user.is_campus_manager and not request.user.is_booking_manager and (profile is None or not profile.is_complete):return redirect('profile')
    from .services import unread_count
    service_unread=unread_count(request.user)
    # 非遗功能暂时停用，不加载推荐资料或服装素材。
    if not settings.ENABLE_HERITAGE:
        return render(request,'campus/home.html',{'service_unread':service_unread,'profile':profile,'is_doctor':is_doctor,'heritage_enabled':False})
    province=request.GET.get('province',profile.hometown_province if profile else '')
    if province not in dict(PROVINCES): province=''
    recommended=next((o for o in OUTFITS if province and o['province']==province),None)
    return render(request,'campus/home.html',{'service_unread':service_unread,'profile':profile,'is_doctor':is_doctor,'heritage_enabled':True,'outfits':OUTFITS,'provinces':PROVINCES,'province':province,'recommended':recommended,'initial_outfit':recommended or OUTFITS[1]})
