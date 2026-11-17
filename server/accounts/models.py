from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from .regions import PROVINCES


class StudentImportBatch(models.Model):
    class Status(models.TextChoices):
        PREVIEW = 'preview', '待确认'
        IMPORTED = 'imported', '已导入'
        ROLLED_BACK = 'rolled_back', '已撤销'

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='student_import_batches')
    original_filename = models.CharField('原文件名', max_length=255)
    preview_rows = models.JSONField('待导入数据', default=list, blank=True)
    status = models.CharField('状态', max_length=20, choices=Status.choices, default=Status.PREVIEW)
    total_count = models.PositiveIntegerField('名单数量', default=0)
    created_count = models.PositiveIntegerField('新增数量', default=0)
    skipped_count = models.PositiveIntegerField('跳过数量', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    imported_at = models.DateTimeField('导入时间', blank=True, null=True)
    rolled_back_at = models.DateTimeField('撤销时间', blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', '-created_at'], name='student_batch_status_time')]


class Profile(models.Model):
    class Gender(models.TextChoices):
        MALE = 'male', '男'
        FEMALE = 'female', '女'
        OTHER = 'other', '其他 / 不便透露'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='guide_profile')
    student_number = models.CharField('学号', max_length=20, blank=True, default='', db_index=True)
    must_change_password = models.BooleanField('首次登录需修改密码', default=False)
    import_batch = models.ForeignKey(StudentImportBatch, on_delete=models.SET_NULL, blank=True, null=True, related_name='student_profiles')
    full_name = models.CharField('姓名', max_length=50)
    gender = models.CharField('性别', max_length=10, choices=Gender.choices)
    age = models.PositiveSmallIntegerField('年龄', blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(120)])
    hometown_province = models.CharField('生源地省份',max_length=20,blank=True,default='',choices=PROVINCES)
    hometown_city = models.CharField('生源地城市',max_length=40,blank=True,default='')
    created_at = models.DateTimeField('注册时间', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student_number'], condition=~models.Q(student_number=''), name='unique_nonempty_student_no'),
            models.CheckConstraint(condition=models.Q(age__isnull=True) | models.Q(age__lte=120), name='student_age_bounds'),
        ]

    @property
    def is_complete(self):
        return bool(self.full_name.strip() and self.gender in self.Gender.values)

    def __str__(self):
        return self.user.username
