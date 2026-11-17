from django.conf import settings
from django.db import models


class Department(models.Model):
    slug = models.SlugField('科室标识', unique=True)
    name = models.CharField('科室名称', max_length=40)
    active = models.BooleanField('启用', default=True)

    def __str__(self):
        return self.name


class DoctorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='doctor_profile')
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='doctors')
    display_name = models.CharField('医生姓名', max_length=50)
    active = models.BooleanField('启用医生入口', default=True)

    def __str__(self):
        return f'{self.department} · {self.display_name}'


class Consultation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='advanced_consultations')
    request_key = models.UUIDField()
    part = models.CharField('部位', max_length=24)
    detail = models.CharField('具体位置', max_length=40, blank=True)
    description = models.TextField('症状描述', max_length=2000)
    followup_answers = models.JSONField('逐步追问记录', default=dict, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, related_name='consultations', verbose_name='分诊科室')
    ai_report = models.JSONField('AI 初步整理', default=dict, blank=True)
    doctor_medication_reference = models.JSONField('医生端用药参考', default=dict, blank=True)
    duration = models.CharField('持续时间', max_length=60, blank=True)
    feeling = models.CharField('用户自述程度', max_length=12)
    level = models.CharField('演示分级', max_length=10)
    emergency = models.BooleanField('出现紧急提示词', default=False)
    status = models.CharField('处理状态', max_length=10, choices=[('pending', '待医生回答'), ('replied', '已回复')], default='pending')
    doctor_reply = models.TextField('医生回复', max_length=5000, blank=True)
    replied_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='triage_replies')
    replied_at = models.DateTimeField('回复时间', null=True, blank=True)
    reply_read = models.BooleanField('回复已读', default=False)
    created_at = models.DateTimeField('提交时间', auto_now_add=True)

    class Meta:
        verbose_name = '高级导诊咨询'
        verbose_name_plural = '高级导诊咨询'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['department', 'status', '-created_at'], name='triage_department_queue')]
        constraints = [models.UniqueConstraint(fields=['user', 'request_key'], name='unique_triage_submission')]

    @property
    def code(self):
        return f'GD{self.pk:06d}'

    def __str__(self):
        return self.code


class CaseConference(models.Model):
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='conferences')
    requested_by = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name='conference_requests')
    target_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='conference_invitations')
    reason = models.CharField('会诊原因', max_length=500)
    status = models.CharField(max_length=12, default='pending', choices=[('pending','待接受'),('accepted','已接受'),('declined','已拒绝'),('revoked','已撤回')])
    accepted_by = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, null=True, blank=True, related_name='accepted_conferences')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['consultation', 'target_department'], name='one_conference_per_department')]


class DiscussionMessage(models.Model):
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='discussion')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT)
    content = models.TextField('内部讨论', max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']


class RoomAppointment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='room_appointments')
    room = models.CharField('诊室', max_length=20)
    starts_at = models.DateTimeField('开始时间')
    ends_at = models.DateTimeField('结束时间')
    number = models.PositiveSmallIntegerField('时段内序号')
    request_key = models.UUIDField()
    status = models.CharField('状态', max_length=12, choices=[('confirmed', '已预约'), ('cancelled', '已取消')], default='confirmed')
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['starts_at', 'number']
        verbose_name = '诊室预约'
        verbose_name_plural = '诊室预约'
        constraints = [
            models.UniqueConstraint(fields=['room', 'starts_at', 'number'], condition=models.Q(status='confirmed'), name='unique_active_room_ticket'),
            models.UniqueConstraint(fields=['user', 'starts_at'], condition=models.Q(status='confirmed'), name='unique_patient_appointment_time'),
            models.UniqueConstraint(fields=['user', 'request_key'], name='unique_room_booking_request'),
            models.CheckConstraint(condition=models.Q(number__gte=1, number__lte=5), name='room_ticket_capacity'),
            models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='room_time_order'),
        ]

    @property
    def code(self):
        return f'RM{self.pk:06d}'
