"""Bounded first-party checks, not an external vulnerability scanner."""
from collections import Counter
from contextlib import closing
from datetime import timedelta
import hashlib,os,re,socket,sqlite3,time,uuid,tempfile,shutil
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection,transaction
from django.utils import timezone
from .models import SecurityScan,SecurityFinding,SecurityBackup,SecurityEvent,StaffAuditEvent
from .database_health import inspect_database

def database_path():
    if connection.vendor!='sqlite':raise ValueError('SQLite only')
    path=Path(connection.settings_dict['NAME']).resolve()
    if not path.is_file():raise ValueError('Database file unavailable')
    return path

def backup_folder():
    base=Path(settings.BASE_DIR).resolve();folder=(base/'runtime/security_backups').resolve()
    if not folder.is_relative_to(base):raise ValueError('Backup directory outside project')
    return folder

def backup_path(row):
    if not re.fullmatch(r'security-[a-f0-9]{32}\.sqlite3',row.filename):raise ValueError('Invalid backup name')
    folder=backup_folder();path=(folder/row.filename).resolve()
    if not path.is_relative_to(folder):raise ValueError('Invalid backup path')
    return path

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def quick_check(path):
    if path.stat().st_size<100:raise ValueError('Empty database file')
    with path.open('rb') as stream:
        if stream.read(16)!=b'SQLite format 3\x00':raise ValueError('Not a SQLite database')
    deadline=time.monotonic()+8
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=3)) as db:
        db.set_progress_handler(lambda:1 if time.monotonic()>deadline else 0,10000)
        return db.execute('PRAGMA quick_check(1)').fetchone()[0]=='ok'

def verify_backup(row):
    path=backup_path(row)
    valid=path.is_file() and digest(path)==row.digest and inspect_database(path,full=True)['healthy']
    row.status='verified' if valid else 'failed';row.verified_at=timezone.now();row.save(update_fields=['status','verified_at'])
    return valid

def create_backup(user):
    source=database_path();folder=backup_folder();folder.mkdir(parents=True,exist_ok=True)
    key=uuid.uuid4();filename='security-'+key.hex+'.sqlite3';target=folder/filename
    deadline=time.monotonic()+20
    def progress(*_):
        if time.monotonic()>deadline:raise TimeoutError('Backup timed out')
    # Partial files are never listed as successful backups.
    partial=target.with_suffix('.partial')
    try:
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=3)) as old,closing(sqlite3.connect(partial,timeout=3)) as new:
            old.backup(new,pages=128,progress=progress,sleep=.05)
            # Backup is a portable, standalone file, including when the live DB uses WAL.
            new.execute('PRAGMA journal_mode=DELETE')
        if not inspect_database(partial,full=True)['healthy']:raise ValueError('Backup check failed')
        partial.replace(target)
        return SecurityBackup.objects.create(id=key,filename=filename,actor=user,size=target.stat().st_size,digest=digest(target),verified_at=timezone.now())
    except Exception:
        for path in (partial,target):
            if path.is_file():path.unlink()
        raise


def rehearse_backup(row):
    """Restore to a temporary PRIVATE copy. Never overwrite the live database."""
    try:
        if not verify_backup(row):
            report={'healthy':False,'error':'backup_verification_failed'}
        else:
            folder=backup_folder()
            with tempfile.TemporaryDirectory(prefix='restore-',dir=folder) as temp:
                target=Path(temp)/'restored.sqlite3'
                shutil.copyfile(backup_path(row),target)
                report=inspect_database(target,full=True)
                report['digest_matches']=digest(target)==row.digest
                report['healthy']=bool(report['healthy'] and report['digest_matches'])
    except (OSError,ValueError,sqlite3.Error):
        # A failed attempt must replace any previous pass, including from the CLI.
        # Copy/permission failures alone do not establish that the backup is corrupt.
        report={'healthy':False,'error':'rehearsal_incomplete'}
    row.restored_at=timezone.now();row.restore_status='passed' if report['healthy'] else 'failed'
    row.restore_report=report;row.save(update_fields=['restored_at','restore_status','restore_report'])
    return report

def local_port(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=.25):return True
    except OSError:return False

def collect():
    checks=[];inventory={}
    def add(code,title,status,evidence,advice,weight=5,group='configuration'):
        checks.append(dict(code=code,title=title,status=status,evidence=evidence,recommendation=advice,weight=weight,group=group,severity='high' if status=='fail' else 'medium' if status=='warn' else 'info'))
    mw=settings.MIDDLEWARE;debug=settings.DEBUG
    add('debug','调试信息暴露','warn' if debug else 'pass','开发模式开启' if debug else '开发模式关闭','对外部署前关闭 DEBUG；本机演示可保留。',8)
    hosts=settings.ALLOWED_HOSTS
    add('host','访问主机限制','fail' if '*' in hosts or not hosts else 'pass','存在通配主机' if '*' in hosts else '已配置明确的访问主机','使用明确的域名或本机地址，避免通配主机。',8,'network')
    add('csrf','请求伪造防护','pass' if 'django.middleware.csrf.CsrfViewMiddleware' in mw else 'fail','检测 Django CSRF 中间件配置','保持 CSRF 中间件启用，写操作使用 POST 与令牌。',10)
    add('cookies','会话 Cookie 保护','pass' if settings.SESSION_COOKIE_HTTPONLY and settings.SESSION_COOKIE_SAMESITE in ('Lax','Strict') else 'fail','检查 HttpOnly 与 SameSite 标志','启用 HttpOnly 及合适的 SameSite。',8)
    tls=settings.SECURE_SSL_REDIRECT and settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
    add('tls','HTTPS 部署基线','pass' if tls else 'warn' if debug else 'fail','检查 HTTPS 跳转和 Secure Cookie 配置','公网部署配置 TLS、HTTPS 跳转及 Secure Cookie；本机 HTTP 为演示状态。',8,'network')
    add('frame','页面嵌入保护','pass' if 'django.middleware.clickjacking.XFrameOptionsMiddleware' in mw else 'warn','检测防点击劫持中间件','保持页面嵌入保护启用。',4)
    add('key','应用密钥配置','pass' if len(settings.SECRET_KEY)>=32 and not settings.SECRET_KEY.startswith('django-insecure-') else 'fail','仅检查密钥长度与开发前缀，不读取展示内容','使用足够长的独立密钥，切勿公开或提交到代码仓库。',8)
    add('admin','启用的总管理员','pass' if get_user_model().objects.filter(is_superuser=True,is_active=True).count()<=3 else 'warn','启用的总管理员数量：'+str(get_user_model().objects.filter(is_superuser=True,is_active=True).count()),'按最小权限保留必要的总管理员账号。',5,'identity')
    try:
        path=database_path();health=inspect_database(path);healthy=health['integrity_ok']
        inventory['database']={**health,'engine':'SQLite','quick_check':healthy,'tables':[]}
        add('db_integrity','数据库结构快速检查','unknown' if healthy is None else 'pass' if healthy else 'fail','只读执行 SQLite quick_check；不等同完整约束与索引核验','检查失败时先备份，再由管理员离线排查，勿直接修改业务数据。',12,'database')
        fk=health['foreign_key_errors']
        add('db_foreign_keys','数据库关联完整性','unknown' if fk is None else 'pass' if fk==0 else 'fail','检查账号、预约和业务记录之间的外键关联','关联异常时保留备份并人工核查，不自动删除记录。',10,'database')
        roots=[Path(settings.MEDIA_ROOT).resolve(),*(Path(p).resolve() for p in settings.STATICFILES_DIRS)]
        exposed=any(path.is_relative_to(root) for root in roots)
        add('db_webroot','数据库静态目录隔离','fail' if exposed else 'pass','检查数据库是否位于配置的静态／媒体目录内','把数据库保存在非公开目录，并复核反向代理规则。',10,'database')
        folder=backup_folder();outside=not any(folder.is_relative_to(root) for root in roots)
        add('backup_webroot','备份目录隔离','pass' if outside else 'fail','备份仅保存在本机项目私有运行目录，不提供数据库下载接口','避免把备份放在 static、media 或公开网盘。',7,'database')
        allowed=[('auth_user','账号'),('帖子_post','论坛帖子'),('跑腿_task','跑腿订单'),('triage_consultation','导诊记录'),('campus_venuebooking','场地预约'),('campus_staffauditevent','操作审计')]
        with connection.cursor() as cur:
            available=set(connection.introspection.table_names())
            for table,label in allowed:
                if table in available:
                    cur.execute('SELECT COUNT(*) FROM '+connection.ops.quote_name(table));inventory['database']['tables'].append({'name':label,'rows':cur.fetchone()[0]})
    except (OSError,ValueError,sqlite3.Error):
        add('db_integrity','数据库结构快速检查','unknown','未能完成本地 SQLite 只读检查','检查运行环境与文件权限后重试。',12,'database')
    latest=SecurityBackup.objects.filter(status='verified').first()
    try:valid_backup=bool(latest and backup_path(latest).is_file() and digest(backup_path(latest))==latest.digest)
    except (OSError,ValueError):valid_backup=False
    recent=bool(valid_backup and latest.created_at>=timezone.now()-timedelta(days=1))
    add('backup_recent','最近一次受管备份','pass' if recent else 'warn','24 小时内有已校验备份' if recent else '24 小时内没有安全中心已校验的备份','在数据库与备份页创建本机备份并定期校验。',8,'database')
    start=timezone.now()-timedelta(hours=24)
    counts=Counter(SecurityEvent.objects.filter(created_at__gte=start).values_list('kind',flat=True))
    inventory['events']={name:counts[name] for name in ['login_failed','permission_denied','not_found','server_error']}
    add('auth_events','登录失败事件','warn' if counts['login_failed']>=10 else 'pass','近 24 小时记录 '+str(counts['login_failed'])+' 次登录失败；上线后开始采集','集中失败时检查账号来源，必要时接入网关限速与登录保护。',5,'identity')
    add('errors','应用错误事件','warn' if counts['server_error'] else 'pass','近 24 小时记录 '+str(counts['server_error'])+' 次服务器错误','查看服务日志定位原因；不要把异常正文或令牌展示给普通用户。',4,'audit')
    add('audit','管理操作审计','pass','已接入角色管理与后台状态变更审计','定期复核总管理员及业务管理员的操作记录。',5,'audit')
    drill=SecurityBackup.objects.filter(restore_status='passed',status='verified').order_by('-restored_at').first()
    try:drill_valid=bool(drill and backup_path(drill).is_file() and digest(backup_path(drill))==drill.digest)
    except (OSError,ValueError):drill_valid=False
    fresh=drill_valid and drill.restored_at and drill.restored_at>=timezone.now()-timedelta(days=7)
    add('restore','备份隔离恢复演练','pass' if fresh else 'warn' if drill_valid else 'unknown','最近 7 天已在隔离副本验证备份' if fresh else '暂无最近 7 天通过的隔离恢复演练','在数据库与备份页执行隔离演练；不代表已验证服务切换。',5,'database')
    for code,title in [('firewall','主机防火墙策略'),('disk','磁盘加密与文件 ACL'),('cve','依赖漏洞库扫描'),('public_tls','公网证书与端口暴露')]:
        add(code,title,'unknown','尚未接入专用检测或完成验证','由系统管理员使用专用工具核验，此项不计为通过。',5,'external')
    inventory['ai_reachable']=local_port(11434)
    inventory['event_total']=sum(counts.values());inventory['audit_count']=StaffAuditEvent.objects.count()
    inventory['backup_count']=SecurityBackup.objects.count()
    return checks,inventory

def calculate(checks):
    known=[c for c in checks if c['status']!='unknown'];weight=sum(c['weight'] for c in known)
    penalty=sum(c['weight']*(1 if c['status']=='fail' else .5 if c['status']=='warn' else 0) for c in known)
    return (max(0,round(100*(1-penalty/weight))) if weight else 0,round(100*len(known)/len(checks)) if checks else 0)

def run_scan(user=None,daily=False):
    today=timezone.localdate()
    if daily:
        existing=SecurityScan.objects.filter(day=today).first()
        if existing:return existing
    checks,inventory=collect();score,coverage=calculate(checks);now=timezone.now()
    with transaction.atomic():
        scan=SecurityScan.objects.create(day=today,actor=user,score=score,coverage=coverage,checks=checks,inventory=inventory)
        for check in checks:
            if check['status'] in ('fail','warn'):
                issue,created=SecurityFinding.objects.get_or_create(code=check['code'],defaults={'title':check['title'],'severity':check['severity'],'evidence':check['evidence'],'recommendation':check['recommendation']})
                issue.title=check['title'];issue.severity=check['severity'];issue.evidence=check['evidence'];issue.recommendation=check['recommendation'];issue.last_seen=now
                if issue.status=='resolved':issue.status='open'
                issue.save()
            elif check['status']=='pass':SecurityFinding.objects.filter(code=check['code']).exclude(status='resolved').update(status='resolved',last_seen=now)
    return scan
