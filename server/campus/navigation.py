from django.urls import reverse

def page_navigation(request):
    match=getattr(request,'resolver_match',None)
    if not match or match.url_name=='home' and not match.namespace:return None
    name=match.url_name;namespace=match.namespace;kw=match.kwargs
    target,label='home','返回校园主页'
    if namespace=='campus':
        parent={
          'booking-admin':('management','返回管理入口'), 'waitlist-admin':('campus:booking-admin','返回预约管理'),
          'service-card':('campus:booking-mine','我的预约'), 'meaning-check':('task-assistant','校园办事向导'), 'booking-preview':('campus:booking-venue','返回场地列表'), 'waitlist':('campus:booking-mine','我的预约'),
          'post_edit':('campus:post_detail','返回帖子'), 'post_delete':('campus:post_detail','返回帖子'), 'report':('campus:post_detail','返回帖子'), 'post_detail':('campus:home','返回广场'),
          'post_create':('campus:home','返回广场'),
          'profile_edit':('campus:profile','返回个人信息'), 'recharge':('campus:profile','返回个人信息'),
          'demo-checkout':('campus:recharge','返回充值记录'),
          'chat':('campus:inbox','返回消息列表'), 'member':('campus:home','返回广场'),
          'errand_detail':('campus:errands','返回跑腿广场'), 'errand_create':('campus:errands','返回跑腿广场'),
          'errand_mine':('campus:errands','返回跑腿广场'), 'errand_questions':('campus:errands','返回跑腿广场'),
          'errand_question':('campus:errand_questions','返回咨询列表'),
          'booking-venue':('campus:booking','返回场地列表'), 'booking-mine':('campus:booking','返回场地列表'),
          'booking-venue-edit':('campus:booking-admin','返回预约管理'),
          'admin_errand':('campus:admin_errands','返回订单列表'), 'admin_question':('campus:admin_questions','返回咨询列表'),
          'review_recharge':('campus:recharges','返回充值审核'), 'review_risk':('campus:risk_alerts','返回风险列表'),
          'review_report':('campus:dashboard','返回管理工作台'),
        }
        if name in parent:target,label=parent[name]
        elif request.path.startswith('/campus-admin/'):
            if name!='dashboard':target,label='campus:dashboard','返回管理工作台'
            elif request.user.is_superuser:target,label='staff-overview','返回总管理工作台'
            else:target,label='management','返回管理入口'
    elif name.startswith('security-') or name in ('management-accounts','staff-audit'):
        target,label='staff-overview','返回总管理工作台'
    elif name=='staff-overview':target,label='management','返回管理入口'
    elif name.startswith('doctor-') and name not in ('doctor-login','doctor-dashboard'):
        target,label=('doctor-drugs','返回药品列表') if name=='doctor-drug-detail' else ('doctor-dashboard','返回医生工作台')
    elif name=='doctor-dashboard':target,label='management','返回管理入口'
    elif name=='management-login':target,label='management','返回管理入口'
    elif name in ('profile',):target,label='guide','返回导诊首页'
    args=[kw['pk']] if target in ('campus:post_detail','campus:booking-venue') else None
    url=reverse(target,args=args)
    return {'url':url,'label':label,'home':reverse('home'),'show_home':target!='home','guide':name=='guide'}
