from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator,MaxValueValidator
import uuid
from django.utils import timezone


class FriendPreference(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='friend_preference')
    country=models.CharField('国家／地区（选填）',max_length=8,blank=True,choices=[('CN','中国'),('RU','俄罗斯'),('JP','日本'),('US','美国'),('GB','英国'),('other','其他')])
    language=models.CharField('聊天接收语言',max_length=2,default='zh',choices=[('zh','中文'),('en','English'),('ru','Русский'),('ja','日本語')])

class FriendMoment(models.Model):
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    content=models.TextField('分享日常',max_length=2000)
    created_at=models.DateTimeField(auto_now_add=True)
    is_hidden=models.BooleanField(default=False)

class SharedBooking(models.Model):
    message=models.OneToOneField('帖子.chat_message',on_delete=models.CASCADE,related_name='campus_booking_share')
    booking=models.ForeignKey('VenueBooking',on_delete=models.CASCADE)
    created_at=models.DateTimeField(auto_now_add=True)

class SecurityScan(models.Model):
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    day=models.DateField(db_index=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    score=models.PositiveSmallIntegerField()
    coverage=models.PositiveSmallIntegerField()
    checks=models.JSONField(default=list)
    inventory=models.JSONField(default=dict)
    class Meta:ordering=['-created_at','-pk']

class SecurityFinding(models.Model):
    code=models.CharField(max_length=60,unique=True)
    title=models.CharField(max_length=120)
    severity=models.CharField(max_length=12)
    evidence=models.CharField(max_length=400)
    recommendation=models.CharField(max_length=400)
    status=models.CharField(max_length=12,default='open',choices=[('open','待处理'),('tracking','跟进中'),('resolved','复查通过')])
    first_seen=models.DateTimeField(auto_now_add=True)
    last_seen=models.DateTimeField(default=timezone.now)
    note=models.CharField(max_length=400,blank=True)
    class Meta:ordering=['status','-last_seen']

class SecurityBackup(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    filename=models.CharField(max_length=100,unique=True)
    created_at=models.DateTimeField(auto_now_add=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    size=models.PositiveBigIntegerField(default=0)
    digest=models.CharField(max_length=64,blank=True)
    verified_at=models.DateTimeField(null=True,blank=True)
    status=models.CharField(max_length=12,default='verified',choices=[('verified','校验通过'),('failed','校验失败')])
    restored_at=models.DateTimeField(null=True,blank=True)
    restore_status=models.CharField(max_length=12,default='pending',choices=[('pending','未演练'),('passed','演练通过'),('failed','演练失败')])
    restore_report=models.JSONField(default=dict,blank=True)
    class Meta:ordering=['-created_at']

class DatabaseInspection(models.Model):
    """Aggregate database evidence only. Author: UniVerse Team."""
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='+')
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    healthy=models.BooleanField(default=False)
    report=models.JSONField(default=dict)
    class Meta:ordering=['-created_at','-pk']

class SecurityEvent(models.Model):
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    kind=models.CharField(max_length=24,db_index=True)
    route=models.CharField(max_length=100,blank=True)
    method=models.CharField(max_length=12,blank=True)
    status_code=models.PositiveSmallIntegerField(default=0)
    class Meta:ordering=['-created_at']


class DemoTopUp(models.Model):
    """Simulated money only; never a third-party payment confirmation."""
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='demo_topups')
    request_key=models.UUIDField()
    amount=models.DecimalField(max_digits=8,decimal_places=2)
    method=models.CharField(max_length=12,choices=[('alipay','支付宝（模拟）'),('wechat','微信支付（模拟）')])
    status=models.CharField(max_length=12,default='pending',choices=[('pending','待模拟支付'),('paid','模拟支付成功'),('cancelled','已取消'),('failed','模拟支付失败'),('expired','已超时')])
    created_at=models.DateTimeField(auto_now_add=True)
    expires_at=models.DateTimeField()
    paid_at=models.DateTimeField(null=True,blank=True)

    class Meta:
        ordering=['-created_at']
        constraints=[models.UniqueConstraint(fields=['user','request_key'],name='unique_demo_topup_request'),models.CheckConstraint(condition=models.Q(amount__gte=1,amount__lte=500),name='demo_topup_amount_bounds')]

    @property
    def reference(self):return 'DEMO-'+self.pk.hex.upper()


class StaffAuditEvent(models.Model):
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='campus_audit_events')
    actor_name=models.CharField(max_length=150)
    module=models.CharField(max_length=20)
    action=models.CharField(max_length=80)
    target=models.CharField(max_length=100)
    changed_fields=models.JSONField(default=list)
    before_state=models.JSONField(default=dict)
    after_state=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)

    class Meta:
        ordering=['-created_at','-pk']

    @property
    def target_reference(self):
        return '#'+self.target.rsplit(':',1)[-1]

    def state_label(self,state):
        labels={'pending':'待处理','replied':'已回复','approved':'已通过','rejected':'已拒绝','kept':'已保留','hidden':'已隐藏','cleared':'已确认正常','accepted':'已接受','declined':'已拒绝','revoked':'已撤回','closed':'已解决','tracking':'跟进中','resolved':'复查通过','verified':'校验通过'}
        if 'status' in state:return labels.get(state['status'],state['status'])
        for key in ('active','is_active'):
            if key in state:return '启用' if state[key] else '停用'
        return ''

    @property
    def before_label(self):return self.state_label(self.before_state)

    @property
    def after_label(self):return self.state_label(self.after_state)

class ImportedCampusUser(models.Model):
    source_id=models.PositiveBigIntegerField(unique=True)
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)

    class Meta:
        permissions=[('manage_campus','管理校园论坛和跑腿'), ('manage_bookings','管理校园场地预约')]

class CampusImportState(models.Model):
    source_key=models.CharField(max_length=200,unique=True)
    completed_at=models.DateTimeField(auto_now_add=True)

VENUE_TYPES=[('study','自习室'),('basketball','篮球场'),('badminton','羽毛球场'),('table_tennis','乒乓球台'),('football','足球场')]
STUDY_BUILDINGS=[('A','A 楼'),('B','B 楼'),('C','C 楼'),('library','图书馆'),('other','其他楼栋')]
TIME_SLOTS=[('08','08:00–10:00'),('10','10:00–12:00'),('14','14:00–16:00'),('16','16:00–18:00'),('18','18:00–20:00')]

class Venue(models.Model):
    name=models.CharField('场地／座位名称',max_length=60)
    kind=models.CharField('类型',max_length=16,choices=VENUE_TYPES)
    building=models.CharField('楼栋',max_length=16,choices=STUDY_BUILDINGS,default='other',help_text='自习室所属楼栋；运动场地可保持其他楼栋。')
    floor=models.PositiveSmallIntegerField('楼层',default=1,validators=[MinValueValidator(1),MaxValueValidator(20)])
    map_area=models.CharField('地图区域',max_length=16,blank=True,default='',choices=[('','按自习楼栋'),('gym','体育馆'),('outdoor','室外足球场')])
    location=models.CharField('位置说明',max_length=100,blank=True)
    description=models.CharField('预约说明',max_length=400,blank=True)
    active=models.BooleanField('开放预约',default=True)
    is_demo=models.BooleanField('示例资源',default=True)

    class Meta:
        ordering=['kind','name','pk']
        indexes=[models.Index(fields=['active','kind','building','floor'],name='venue_map_filter')]
        constraints=[models.CheckConstraint(condition=models.Q(floor__gte=1,floor__lte=20),name='venue_floor_bounds')]

    def __str__(self):return self.name

class VenueBooking(models.Model):
    venue=models.ForeignKey(Venue,on_delete=models.PROTECT,related_name='bookings')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='venue_bookings')
    day=models.DateField('预约日期')
    slot=models.CharField('时段',max_length=2,choices=TIME_SLOTS)
    status=models.CharField('状态',max_length=12,choices=[('reserved','已预约'),('cancelled','已取消'),('no_show','超时未到，已释放'),('released','管理员已释放')],default='reserved')
    request_key=models.UUIDField()
    created_at=models.DateTimeField(auto_now_add=True)
    cancelled_at=models.DateTimeField(null=True,blank=True)
    checkin_deadline=models.DateTimeField(null=True,blank=True)
    checked_in_at=models.DateTimeField(null=True,blank=True)
    released_at=models.DateTimeField(null=True,blank=True)
    released_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='released_seat_bookings')
    release_reason=models.CharField(max_length=200,blank=True)

    class Meta:
        ordering=['-day','slot','-pk']
        indexes=[
            models.Index(fields=['status','checked_in_at','checkin_deadline'],name='booking_checkin_due'),
            models.Index(fields=['user','-day','slot'],name='booking_user_calendar'),
        ]
        constraints=[
            models.CheckConstraint(condition=models.Q(slot__in=['08','10','14','16','18']),name='booking_valid_slot'),
            models.CheckConstraint(condition=models.Q(status__in=['reserved','cancelled','no_show','released']),name='booking_valid_status'),
            models.UniqueConstraint(fields=['venue','day','slot'],condition=models.Q(status='reserved'),name='one_active_booking_per_venue_slot'),
            models.UniqueConstraint(fields=['user','day','slot'],condition=models.Q(status='reserved'),name='one_venue_per_user_slot'),
            models.UniqueConstraint(fields=['user','request_key'],name='unique_venue_submission'),
        ]


class VenueWaitlist(models.Model):
    venue=models.ForeignKey(Venue,on_delete=models.PROTECT,related_name='waitlist')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='venue_waitlist')
    day=models.DateField()
    slot=models.CharField(max_length=2,choices=TIME_SLOTS)
    status=models.CharField(max_length=12,default='waiting',choices=[('waiting','候补中'),('offered','待确认名额'),('claimed','已确认预约'),('cancelled','已退出'),('expired','已过期'),('ineligible','同时间已有预约')])
    created_at=models.DateTimeField(auto_now_add=True)
    offered_until=models.DateTimeField(null=True,blank=True)
    booking=models.OneToOneField(VenueBooking,on_delete=models.SET_NULL,null=True,blank=True,related_name='waitlist_claim')
    claimed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering=['created_at','pk']
        indexes=[
            models.Index(fields=['status','offered_until'],name='waitlist_offer_expiry'),
            models.Index(fields=['venue','day','slot','status','created_at'],name='waitlist_fifo_lookup'),
        ]
        constraints=[
            models.CheckConstraint(condition=models.Q(slot__in=['08','10','14','16','18']),name='waitlist_valid_slot'),
            models.CheckConstraint(condition=models.Q(status__in=['waiting','offered','claimed','cancelled','expired','ineligible']),name='waitlist_valid_status'),
            models.UniqueConstraint(fields=['venue','day','slot','user'],condition=models.Q(status__in=['waiting','offered']),name='one_live_waitlist_per_user_resource'),
            models.UniqueConstraint(fields=['venue','day','slot'],condition=models.Q(status='offered'),name='one_waitlist_offer_per_resource'),
        ]


class CampusServicePlan(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='service_plans')
    source=models.CharField(max_length=2000)
    kind=models.CharField(max_length=20,blank=True)
    steps=models.JSONField(default=list)
    completed=models.JSONField(default=list)
    accepted=models.BooleanField(default=False)
    day=models.DateField(null=True,blank=True)
    slot=models.CharField(max_length=2,blank=True)
    state=models.CharField(max_length=12,default='active',choices=[('active','进行中'),('completed','已完成'),('cancelled','已结束')])
    booking=models.ForeignKey(VenueBooking,on_delete=models.SET_NULL,null=True,blank=True,related_name='service_plans')
    workflow_version=models.PositiveSmallIntegerField(default=1)
    linked_post=models.ForeignKey('帖子.post',on_delete=models.SET_NULL,null=True,blank=True,related_name='campus_plans')
    shared_message=models.ForeignKey('帖子.chat_message',on_delete=models.SET_NULL,null=True,blank=True,related_name='campus_plans')
    navigation_started_at=models.DateTimeField(null=True,blank=True)
    skipped=models.JSONField(default=list)
    revision=models.UUIDField(default=uuid.uuid4)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['-updated_at','-pk']
        constraints=[models.UniqueConstraint(fields=['user'],condition=models.Q(state='active'),name='one_active_service_plan')]


class AIInvocation(models.Model):
    provider=models.CharField(max_length=20,choices=[('ollama','本地 Ollama'),('deepseek','DeepSeek 官方')],db_index=True)
    model=models.CharField(max_length=150)
    success=models.BooleanField(default=False)
    duration_ms=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    class Meta:ordering=['-created_at','-pk']


class BookingNotice(models.Model):
    """Persistent, owner-scoped station messages. 制作：UniVerse Team。"""
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='booking_notices')
    kind=models.CharField(max_length=24,choices=[('checkin_reminder','签到提醒'),('seat_released','座位已释放'),('waitlist_offer','候补名额通知')])
    event_key=models.CharField(max_length=100,unique=True)
    booking=models.ForeignKey(VenueBooking,on_delete=models.SET_NULL,null=True,blank=True,related_name='notices')
    waitlist=models.ForeignKey(VenueWaitlist,on_delete=models.SET_NULL,null=True,blank=True,related_name='notices')
    is_read=models.BooleanField(default=False,db_index=True)
    read_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-created_at','-pk']
        indexes=[models.Index(fields=['user','is_read','-created_at'],name='notice_user_unread')]
