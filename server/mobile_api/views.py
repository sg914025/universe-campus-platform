"""Shared mobile API. Author: UniVerse Team. Calls the existing campus business services."""
import json, re, uuid, hashlib, mimetypes
from datetime import date, timedelta
from pathlib import Path
from importlib import import_module
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, get_user, get_user_model, update_session_auth_hash
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.forms import PasswordChangeForm
from django.core.cache import cache
from django.core import signing
from django.db import transaction, IntegrityError, OperationalError
from django.db.models import Q
from django.http import JsonResponse, Http404, FileResponse, QueryDict
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from campus.models import Venue, VenueBooking, VenueWaitlist, TIME_SLOTS, STUDY_BUILDINGS, VENUE_TYPES, FriendPreference, FriendMoment, SharedBooking
from campus import service_plans, task_assistant, waitlist, attendance, home_weather, friend_services, services
from campus.booking_forms import BookingForm, slot_start
from 帖子.models import post, profile, follow, chat_message, categories, announcement
from 个人信息.social import friends_for, are_friends, unread_for


def reply(data, status=200):
    response=JsonResponse(data,status=status)
    response['Cache-Control']='private, no-store'
    return response


def name(user):
    person=getattr(user,'profile',None)
    return person.nickname if person and person.nickname else user.username


def me(user):
    p=getattr(user,'guide_profile',None)
    return {'id':user.pk,'name':name(user),'username':user.username,'must_change_password':bool(p and p.must_change_password),'profile_complete':bool(p and p.is_complete)}


def body(request):
    if len(request.body)>65000:raise ValueError('提交内容过长')
    if request.content_type!='application/json':raise ValueError('请使用 JSON 请求')
    data=json.loads(request.body or '{}')
    if not isinstance(data,dict):raise ValueError('请求格式不正确')
    return data


def text(data,key,limit=2000,required=True):
    value=data.get(key,'')
    if not isinstance(value,str) or len(value)>limit or required and not value.strip():raise ValueError('请检查 '+key)
    return value.strip()


def query_form(request,data):
    request.POST=QueryDict('',mutable=True)
    for key,value in data.items():request.POST[key]=str(value)


def booking_row(row):
    return {'id':row.pk,'venue_id':row.venue_id,'name':row.venue.name,'kind':row.venue.kind,'building':row.venue.get_building_display(),'floor':row.venue.floor,'location':row.venue.location,'day':row.day.isoformat(),'slot':row.slot,'time':row.get_slot_display(),'status':row.status,'status_label':row.get_status_display(),'checked_in':bool(row.checked_in_at),'deadline':row.checkin_deadline.isoformat() if row.checkin_deadline else None,'can_cancel':row.status=='reserved' and slot_start(row.day,row.slot)>timezone.now()}


def post_row(row):
    return {'id':row.pk,'title':row.title,'content':row.content,'category':row.category,'author':name(row.author),'author_id':row.author_id,'created_at':row.created_at.isoformat(),'image':row.image.url if row.image else ''}


def require_method(request,*methods):
    if request.method not in methods:raise ValueError('不支持的操作方式')


@csrf_exempt
def endpoint(request,route='bootstrap'):
    try:
        if request.method not in ('GET','POST'):return reply({'error':'Method not allowed'},405)
        data=body(request) if request.method=='POST' else {}
        token=request.headers.get('Authorization','')
        request.user=AnonymousUser()
        if token:
            if not re.fullmatch(r'Bearer [a-z0-9]{32}',token):return reply({'error':'请重新登录'},401)
            request.session=import_module(settings.SESSION_ENGINE).SessionStore(session_key=token[7:])
            request.user=get_user(request)
            if not request.user.is_authenticated or not request.user.is_active:return reply({'error':'登录已失效，请重新登录'},401)
        language=request.headers.get('X-Campus-Language','zh')
        if language not in ('zh','en','ru','ja'):language='zh'
        if request.user.is_authenticated:request.session['campus_language']=language
        if route=='auth/login':
            require_method(request,'POST')
            username=text(data,'username',150);password=text(data,'password',512)
            key='mobile-login:'+hashlib.sha256((request.META.get('REMOTE_ADDR','')+'|'+username.casefold()).encode()).hexdigest()
            if cache.get(key,0)>=10:return reply({'error':'尝试次数过多，请十分钟后重试'},429)
            user=authenticate(request,username=username,password=password)
            if not user:
                cache.set(key,cache.get(key,0)+1,600)
                return reply({'error':'学号或密码不正确'},401)
            cache.delete(key)
            request.session=import_module(settings.SESSION_ENGINE).SessionStore()
            login(request,user);request.session.set_expiry(7*86400);request.session['campus_language']=language;request.session.save()
            return reply({'token':request.session.session_key,'user':me(user)})
        if route=='bootstrap':
            require_method(request,'GET')
            return reply({'name':'寰校通 UniVerse','version':'1.0.0','today':timezone.localdate().isoformat(),'default_day':(timezone.localdate()+timedelta(days=1) if timezone.localtime().hour>=18 else timezone.localdate()).isoformat(),'default_slot':next((code for code,label in TIME_SLOTS if int(code)>timezone.localtime().hour),'08'),'kinds':[{'value':k,'label':v} for k,v in VENUE_TYPES],'buildings':[{'value':k,'label':v} for k,v in STUDY_BUILDINGS],'slots':[{'value':k,'label':v} for k,v in TIME_SLOTS],'announcements':list(announcement.objects.filter(is_active=True).values('id','title','content')[:3]),'user':me(request.user) if request.user.is_authenticated else None})
        if route=='weather':
            request.session['campus_language']=language
            require_method(request,'POST')
            return home_weather.api(request)
        if not request.user.is_authenticated:return reply({'error':'请先登录校园账号'},401)
        if route=='auth/logout':
            require_method(request,'POST');logout(request);return reply({'ok':True})
        if route=='auth/password':
            require_method(request,'POST')
            form=PasswordChangeForm(request.user,data)
            if not form.is_valid():return reply({'error':'请检查原密码及新密码','fields':form.errors.get_json_data()},400)
            user=form.save();update_session_auth_hash(request,user)
            p=getattr(user,'guide_profile',None)
            if p:p.must_change_password=False;p.save(update_fields=['must_change_password'])
            request.session.save()
            return reply({'token':request.session.session_key,'user':me(user)})
        if route=='me':
            require_method(request,'GET');return reply({'user':me(request.user)})
        p=getattr(request.user,'guide_profile',None)
        if p and p.must_change_password:return reply({'error':'首次登录请先修改初始密码','code':'password_change_required'},403)
        if route=='web-ticket':
            require_method(request,'POST')
            path=text(data,'path',2000)
            if not path.startswith(('/campus-map/','/errands/','/journey/','/guide/','/booking/','/my-services/','/friends/','/forum/')) or '\\' in path or any(ord(c)<32 for c in path):raise ValueError('无效服务地址')
            ticket=uuid.uuid4().hex+uuid.uuid4().hex
            cache.set('mobile-bridge:'+ticket,{'user':request.user.pk,'hash':request.user.get_session_auth_hash(),'path':path},30)
            return reply({'url':'/mobile/bridge/'+ticket+'/'})
        if route=='overview':
            require_method(request,'GET')
            info=services.personal_services(request.user)
            plan=service_plans.active(request.user)
            return reply({'user':me(request.user),'unread':info['unread_total'],'bookings':[booking_row(x) for x in info['bookings']],'active_errands':info['active_errands'],'pending_consultations':info['pending_consultations'],'plan':service_plans.serialize(request,plan) if plan else None,'notices':info['notices']})
        delegates={'assistant/state':task_assistant.state,'assistant/chat':task_assistant.chat,'assistant/confirm':task_assistant.confirm,'plans':service_plans.endpoint}
        if route in delegates:return delegates[route](request)
        if route=='venues':
            require_method(request,'GET')
            day=date.fromisoformat(request.GET.get('day',timezone.localdate().isoformat()));slot=request.GET.get('slot','14')
            if slot not in dict(TIME_SLOTS) or not timezone.localdate()<=day<=timezone.localdate()+timedelta(days=14):raise ValueError('请选择未来 14 天内的有效时段')
            kind=request.GET.get('kind','study');building=request.GET.get('building','A')
            if kind not in dict(VENUE_TYPES) or building not in dict(STUDY_BUILDINGS):raise ValueError('请选择场地类型和楼栋')
            venues=Venue.objects.filter(active=True,kind=kind)
            if kind=='study':venues=venues.filter(building=building)
            occupied=set(VenueBooking.objects.filter(day=day,slot=slot,status='reserved').values_list('venue_id',flat=True))
            held=set(VenueWaitlist.objects.filter(day=day,slot=slot,status='offered',offered_until__gt=timezone.now()).exclude(user=request.user).values_list('venue_id',flat=True))
            conflict=VenueBooking.objects.filter(user=request.user,day=day,slot=slot,status='reserved').exists()
            rows=[]
            for v in venues.order_by('floor','name')[:240]:
                state='occupied' if v.pk in occupied else 'held' if v.pk in held else 'unavailable' if conflict or not attendance.bookable(v,day,slot) else 'available'
                rows.append({'id':v.pk,'name':v.name,'kind':v.kind,'building':v.building,'floor':v.floor,'location':v.location,'state':state,'is_demo':v.is_demo})
            return reply({'venues':rows,'day':str(day),'slot':slot})
        if route=='bookings':
            if request.method=='GET':return reply({'bookings':[booking_row(x) for x in VenueBooking.objects.filter(user=request.user).select_related('venue')[:100]]})
            venue=get_object_or_404(Venue,pk=int(data.get('venue_id',0)),active=True)
            form=BookingForm(data,venue=venue)
            if not form.is_valid():return reply({'error':'请选择有效的预约时间','fields':form.errors.get_json_data()},400)
            item=waitlist.reserve(request.user,venue,**form.cleaned_data)
            return reply({'booking':booking_row(item)},201)
        match=re.fullmatch(r'bookings/(\d+)/(cancel|checkin|share|navigation)',route)
        if match:
            pk,action=match.groups();item=get_object_or_404(VenueBooking.objects.select_related('venue'),pk=int(pk),user=request.user)
            if action=='navigation':
                require_method(request,'GET')
                from campus.checkin_views import map_url
                return reply({'booking':booking_row(item),'url':map_url(item)})
            require_method(request,'POST')
            if action=='cancel':
                if not waitlist.cancel_booking(request.user,item.pk):return reply({'error':'该预约当前不能取消'},409)
                return reply({'ok':True})
            if action=='checkin':
                token=text(data,'token',2000)
                if signing.loads(token,salt='universe-seat-checkin')!={'booking':item.pk,'user':request.user.pk}:return reply({'error':'二维码不属于当前预约'},403)
                row,status=attendance.check_in(request.user,item.pk)
                if status not in ('ok','already'):return reply({'error':{'early':'还未到签到时间','expired':'已超过签到时间','unavailable':'当前预约无需签到或已失效'}.get(status,'暂不能签到')},409)
                return reply({'booking':booking_row(row)})
            friend=get_object_or_404(friends_for(request.user).filter(is_active=True),pk=int(data.get('friend_id',0)))
            with transaction.atomic():
                plan=service_plans.active(request.user)
                if plan and plan.booking_id==item.pk and service_plans.current_step(plan)=='share':
                    if str(plan.revision)!=data.get('revision'):return reply({'error':'请刷新计划后重试'},409)
                else:plan=None
                sent=chat_message.objects.create(sender=request.user,receiver=friend,content='分享了一张办事卡。')
                SharedBooking.objects.create(message=sent,booking=item);service_plans.shared_completed(plan,sent,item)
            return reply({'ok':True})
        if route=='posts':
            if request.method=='GET':
                rows=post.objects.filter(is_hidden=False).select_related('author__profile')
                category=request.GET.get('category','')
                if category:rows=rows.filter(category=category)
                page=max(1,min(int(request.GET.get('page','1')),10000));offset=(page-1)*20
                records=list(rows.order_by('-created_at','-pk')[offset:offset+21])
                return reply({'posts':[post_row(x) for x in records[:20]],'has_more':len(records)>20,'categories':[x[0] for x in categories]})
            from 帖子.forms import post_form
            from 帖子.views import duplicate_post_error,post_fingerprint,store_tags
            from 帖子.risk import flag_content
            with transaction.atomic():
                form=post_form(data)
                if not form.is_valid():return reply({'error':'请检查帖子内容','fields':form.errors.get_json_data()},400)
                error=duplicate_post_error(request.user,form.cleaned_data['title'],form.cleaned_data['content'])
                if error:return reply({'error':error},409)
                plan=None
                if data.get('service_plan'):
                    request.GET=request.GET.copy();request.GET['service_plan']=str(data['service_plan']);request.GET['revision']=data.get('revision','');plan=service_plans.post_plan(request)
                    if form.cleaned_data['category']!='交友':raise ValueError('办事计划需要发布交友帖')
                item=form.save(commit=False);item.author=request.user;item.duplicate_key=post_fingerprint(item.title,item.content);item.save();store_tags(item,form.cleaned_data['tags_text'])
                flag_content('post',item.pk,request.user,item.title+'\n'+item.content);service_plans.post_completed(request,plan,item)
            return reply({'post':post_row(item)},201)
        if route=='friends':
            require_method(request,'GET')
            return reply({'friends':[{'id':u.pk,'name':name(u),'unread':unread_for(request.user).filter(sender=u).count()} for u in friends_for(request.user).filter(is_active=True)[:100]]})
        if route=='friends/search':
            require_method(request,'GET');q=request.GET.get('q','').strip()[:100]
            if len(q)<2:return reply({'people':[]})
            people=get_user_model().objects.filter(is_active=True,profile__isnull=False).filter(Q(username__icontains=q)|Q(profile__nickname__icontains=q)).exclude(pk=request.user.pk)[:20]
            return reply({'people':[{'id':u.pk,'name':name(u),'following':follow.objects.filter(user=request.user,target=u).exists(),'friend':are_friends(request.user,u)} for u in people]})
        match=re.fullmatch(r'friends/(\d+)/(follow|messages)',route)
        if match:
            pk,action=match.groups();target=get_object_or_404(get_user_model(),pk=int(pk),is_active=True)
            if target.pk==request.user.pk:raise ValueError('请选择其他同学')
            if action=='follow':
                require_method(request,'POST');follow.objects.get_or_create(user=request.user,target=target);return reply({'friend':are_friends(request.user,target)})
            if not are_friends(request.user,target):return reply({'error':'双方互相关注后才能聊天'},403)
            if request.method=='POST':
                from 帖子.risk import flag_content
                content=text(data,'content');sent=chat_message.objects.create(sender=request.user,receiver=target,content=content);flag_content('chat',sent.pk,request.user,content)
                return reply({'id':sent.pk},201)
            chat_message.objects.filter(sender=target,receiver=request.user,is_read=False).update(is_read=True)
            rows=chat_message.objects.filter(Q(sender=request.user,receiver=target)|Q(sender=target,receiver=request.user),is_hidden=False).select_related('shared_post','campus_booking_share__booking__venue').order_by('-pk')[:80]
            values=[]
            for row in reversed(list(rows)):
                share=getattr(row,'campus_booking_share',None)
                values.append({'id':row.pk,'mine':row.sender_id==request.user.pk,'content':row.content,'time':row.created_at.isoformat(),'shared_title':row.shared_title,'booking':booking_row(share.booking) if share else None})
            return reply({'messages':values,'peer':{'id':target.pk,'name':name(target)},'auto_translate':friend_services.chat_context(request,target)['friend_auto_translate']})
        match=re.fullmatch(r'messages/(\d+)/translation',route)
        if match:return friend_services.message_translation(request,int(match[1]))
        if route=='moments':
            if request.method=='POST':
                form=friend_services.MomentForm(data)
                if not form.is_valid():return reply({'error':'请检查日常内容','fields':form.errors.get_json_data()},400)
                item=form.save(commit=False);item.author=request.user;item.save();return reply({'id':item.pk},201)
            rows=FriendMoment.objects.filter(Q(author=request.user)|Q(author__in=friends_for(request.user)),is_hidden=False).select_related('author__profile').order_by('-pk')[:40]
            return reply({'moments':[{'id':x.pk,'author':name(x.author),'content':x.content,'time':x.created_at.isoformat()} for x in rows]})
        if route=='notices':
            if request.method=='GET':return reply({'notices':services.personal_services(request.user)['notices']})
            query_form(request,data);result=services.read(request)
            return reply({'ok':True}) if result.status_code==302 else result
        if route=='health/parts':
            require_method(request,'GET');from triage.parts import PARTS
            return reply({'parts':[{'value':key,'label':value['name']} for key,value in PARTS.items()]})
        if route in ('health/followup','health/assess','health/inbox'):
            from triage import views
            return {'health/followup':views.followup,'health/assess':views.assess,'health/inbox':views.inbox}[route](request)
        if route=='errands':
            require_method(request,'GET');from 跑腿.models import task
            rows=task.objects.filter(status='open').select_related('owner').order_by('-pk')[:40]
            return reply({'errands':[{'id':x.pk,'title':x.title,'description':x.description,'category':x.get_category_display(),'price':str(x.price),'status':x.get_status_display(),'owner':name(x.owner)} for x in rows]})
        return reply({'error':'接口不存在'},404)
    except Http404:return reply({'error':'内容不存在或无权查看'},404)
    except signing.BadSignature:return reply({'error':'二维码无效'},400)
    except (ValueError,TypeError,OverflowError):return reply({'error':'请求内容不正确，请检查后重试'},400)
    except IntegrityError:return reply({'error':'状态已变化或预约冲突，请刷新后重试'},409)
    except OperationalError as error:
        if 'locked' not in str(error).lower():raise
        return reply({'error':'当前请求较多，请稍后重试'},503)


def web(request,asset=''):
    """Local integrated H5 output, confined to static/mobile. Production may use nginx."""
    root=(Path(settings.BASE_DIR)/'static/mobile').resolve()
    path=(root/(asset or 'index.html')).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise Http404()
    response=FileResponse(path.open('rb'),content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
    response['Cache-Control']='no-cache' if path.name=='index.html' else 'public, max-age=3600'
    return response


def bridge(request,ticket):
    from django.shortcuts import redirect
    from django.utils.crypto import constant_time_compare
    if request.method!='GET' or not re.fullmatch('[a-f0-9]{64}',ticket):raise Http404()
    if not cache.add('mobile-bridge-used:'+ticket,True,40):raise Http404()
    record=cache.get('mobile-bridge:'+ticket);cache.delete('mobile-bridge:'+ticket)
    if not record:raise Http404()
    user=get_user_model().objects.filter(pk=record['user'],is_active=True).first()
    if not user or not constant_time_compare(user.get_session_auth_hash(),record['hash']):raise Http404()
    p=getattr(user,'guide_profile',None)
    if p and p.must_change_password:raise Http404()
    login(request,user,backend='django.contrib.auth.backends.ModelBackend')
    response=redirect(record['path']);response['Cache-Control']='no-store';response['Referrer-Policy']='no-referrer'
    return response
