from collections import Counter
from datetime import timedelta
import sqlite3
import re
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET,require_POST
from .management_views import role_required
from .models import SecurityScan,SecurityFinding,SecurityBackup,SecurityEvent,DatabaseInspection
from .security_service import run_scan,create_backup,verify_backup,rehearse_backup
from .audit import record_event
from .ui_language import translate

PAGES=[('overview','安全总览'),('twin','数据孪生'),('risks','风险中心'),('database','数据库与备份'),('daily','每日评分'),('ai','AI 调用统计')]

def evidence_text(value,language):
    for pattern,template in [
        (r'^启用的总管理员数量：(\d+)$','启用的总管理员数量：{count}'),
        (r'^近 24 小时记录 (\d+) 次登录失败；上线后开始采集$','近 24 小时记录 {count} 次登录失败；上线后开始采集'),
        (r'^近 24 小时记录 (\d+) 次服务器错误$','近 24 小时记录 {count} 次服务器错误')]:
        match=re.match(pattern,value)
        if match:return translate(template,language).format(count=match[1])
    return translate(value,language)

def context(request,section):
    latest=SecurityScan.objects.first();today=timezone.localdate()
    scans=list(SecurityScan.objects.filter(day__gte=today-timedelta(days=13)).order_by('day','created_at','pk'))
    daily={scan.day:scan for scan in scans};history=[]
    for offset in range(13,-1,-1):
        day=today-timedelta(days=offset);row=daily.get(day)
        history.append({'date':day.isoformat(),'label':day.strftime('%m/%d'),'score':row.score if row else None})
    counts=Counter(c['status'] for c in latest.checks) if latest else Counter()
    t=lambda value:translate(value,request.session.get('campus_language',request.COOKIES.get('campus_language','zh')))
    code=request.session.get('campus_language',request.COOKIES.get('campus_language','zh'))
    checks=[{**c,'evidence':evidence_text(c['evidence'],code),'status_label':t({'pass':'通过','warn':'需关注','fail':'风险','unknown':'未核验'}[c['status']])} for c in latest.checks] if latest else []
    inventory=latest.inventory if latest else {}
    nodes=[
        {'id':'app','label':t('校园应用'),'state':'pass','metric':t('当前页面请求正常'),'position':[0,32,0]},
        {'id':'db','label':t('本地数据库'),'state':'pass' if inventory.get('database',{}).get('quick_check') else 'unknown','metric':t('只读结构检查'),'position':[-170,0,-100]},
        {'id':'ai','label':t('本地 AI'),'state':'pass' if inventory.get('ai_reachable') else 'unknown','metric':t('仅检测本机 11434 端口'),'position':[175,0,-105]},
        {'id':'forum','label':t('论坛与跑腿'),'state':'linked','metric':t('发布前词表校验'),'position':[-165,0,110]},
        {'id':'booking','label':t('预约服务'),'state':'linked','metric':t('服务逻辑关联'),'position':[170,0,115]},
        {'id':'audit','label':t('审计事件'),'state':'pass','metric':str(inventory.get('audit_count',0))+' '+t('条记录'),'position':[0,0,200]},
        {'id':'backup','label':t('本机备份'),'state':next((c['status'] for c in checks if c['code']=='backup_recent'),'unknown'),'metric':str(inventory.get('backup_count',0))+' '+t('份受管备份'),'position':[0,0,-210]},
    ]
    return {'security_section':section,'security_pages':[{'key':key,'label':label,'url':reverse('security-'+key)} for key,label in PAGES],
        'latest':latest,'checks':checks,'counts':{'passed':counts['pass'],'risk':counts['fail']+counts['warn'],'unknown':counts['unknown']},
        'needs_scan':not latest or latest.day!=today,'history':history,'inventory':inventory,
        'risk_count':SecurityFinding.objects.exclude(status='resolved').count(),
        'twin_data':{'nodes':nodes,'links':[['app',n['id']] for n in nodes if n['id']!='app'],'updated':latest.created_at.isoformat() if latest else None},
        'days_with_scores':len(daily)}

@role_required('superadmin')
@require_GET
def page(request,section='overview'):
    if section not in dict(PAGES):return redirect('security-overview')
    data=context(request,section)
    data['findings']=SecurityFinding.objects.exclude(status='resolved').order_by('severity','-last_seen')[:8]
    if section=='risks':
        status=request.GET.get('status','open');rows=SecurityFinding.objects.all()
        if status in ('open','tracking','resolved'):rows=rows.filter(status=status)
        else:status='all'
        data.update(finding_page=Paginator(rows,15).get_page(request.GET.get('page')),filter_status=status,events=SecurityEvent.objects.all()[:20])
    if section=='database':
        from .ai_dashboard import asset_chart
        data['assets']=asset_chart(data['inventory'].get('database',{}).get('tables',[]))
        data['backups']=SecurityBackup.objects.all()[:20]
        data['database_inspection']=DatabaseInspection.objects.first()
        data['database_checks']=DatabaseInspection.objects.all()[:5]
        data['inventory']={**data['inventory'],'backup_count':SecurityBackup.objects.count()}
    if section=='ai':
        from .ai_dashboard import usage_data
        data['usage']=usage_data()
    if section=='daily':data['scan_page']=Paginator(SecurityScan.objects.all(),15).get_page(request.GET.get('page'))
    if section=='risks':
        language=request.session.get('campus_language',request.COOKIES.get('campus_language','zh'))
        for issue in data['finding_page']:issue.evidence=evidence_text(issue.evidence,language)
    return render(request,'campus/security/'+section+'.html',data)

@role_required('superadmin')
@require_POST
def check(request):
    try:
        scan=run_scan(request.user,daily=request.POST.get('daily')=='1')
        if request.POST.get('daily')!='1':record_event(request.user,'superadmin','执行安全体检',scan)
    except (OSError,ValueError,DatabaseError,sqlite3.Error):
        if request.headers.get('X-Requested-With')=='XMLHttpRequest':return JsonResponse({'error':'安全检查未完成，请稍后重试。'},status=503)
        messages.error(request,'安全检查未完成，请稍后重试。');return redirect('security-overview')
    if request.headers.get('X-Requested-With')=='XMLHttpRequest':return JsonResponse({'ok':True,'score':scan.score})
    messages.success(request,'今日安全体检已更新。');return redirect('security-overview')

@role_required('superadmin')
@require_POST
def backup(request):
    try:
        row=create_backup(request.user);record_event(request.user,'superadmin','创建安全备份',row)
        messages.success(request,'本机备份已创建，完整性与外键校验通过。')
    except (OSError,ValueError,TimeoutError,DatabaseError,sqlite3.Error):messages.error(request,'备份未完成，请检查本机存储与权限。')
    return redirect('security-database')

@role_required('superadmin')
@require_POST
def inspect(request):
    from .database_health import record_inspection
    try:
        row=record_inspection(request.user)
        record_event(request.user,'superadmin','执行数据库完整检查',row)
        messages.success(request,'数据库完整检查通过。') if row.healthy else messages.error(request,'数据库检查存在异常或未完成，请查看检查记录。')
    except (OSError,ValueError,DatabaseError,sqlite3.Error):
        messages.error(request,'数据库检查未完成，请稍后重试。')
    return redirect('security-database')

@role_required('superadmin')
@require_POST
def rehearse(request,pk):
    row=get_object_or_404(SecurityBackup,pk=pk)
    try:
        report=rehearse_backup(row)
        record_event(request.user,'superadmin','执行备份隔离恢复演练',row)
        messages.success(request,'隔离恢复演练通过，线上数据库未被覆盖。') if report['healthy'] else messages.error(request,'隔离恢复演练失败，请保留备份并排查。')
    except (OSError,ValueError,DatabaseError,sqlite3.Error):
        row.restore_status='failed';row.restored_at=timezone.now();row.restore_report={'healthy':False,'error':'rehearsal_incomplete'}
        row.save(update_fields=['restore_status','restored_at','restore_report'])
        messages.error(request,'隔离恢复演练未完成，请稍后重试。')
    return redirect('security-database')

@role_required('superadmin')
@require_POST
def verify(request,pk):
    row=get_object_or_404(SecurityBackup,pk=pk)
    try:
        valid=verify_backup(row);record_event(request.user,'superadmin','校验安全备份',row)
        messages.success(request,'备份内容与哈希校验通过。' if valid else '备份校验失败，请保留现场并排查。')
    except (OSError,ValueError,DatabaseError,sqlite3.Error):
        row.status='failed';row.save(update_fields=['status']);messages.error(request,'备份校验失败，请保留现场并排查。')
    return redirect('security-database')

@role_required('superadmin')
@require_POST
def track(request,pk):
    issue=get_object_or_404(SecurityFinding,pk=pk)
    if issue.status!='resolved':
        before=issue.status
        changed=SecurityFinding.objects.filter(pk=issue.pk).exclude(status='resolved').update(status='tracking',note=request.POST.get('note','').strip()[:400])
        if changed:
            record_event(request.user,'superadmin','跟进安全风险',issue,['status'],{'status':before},{'status':'tracking'})
            messages.success(request,'已标记跟进；修复后重新检查才会自动关闭风险。')
    return redirect('security-risks')
