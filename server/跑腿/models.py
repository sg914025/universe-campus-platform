from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

# 送达照片单独保存，必须通过订单权限检查后才能读取。
def proof_storage():
    return FileSystemStorage(location=settings.PRIVATE_UPLOAD_ROOT)
task_types = [('express', '取快递'), ('shopping', '代买东西'), ('delivery', '物品送达'), ('other', '其他帮助')]

class task(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='issued_tasks')
    runner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='taken_tasks')
    title = models.CharField(max_length=80)
    category = models.CharField(max_length=20, choices=task_types, default='express')
    description = models.TextField(max_length=2000)
    address = models.CharField(max_length=300)
    phone = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=20, default='open', choices=[('open', '待接单'), ('accepted', '已接单'), ('delivered', '等待确认'), ('completed', '已完成'), ('cancelled', '已取消')])
    proof = models.ImageField(storage=proof_storage, upload_to='errands/', blank=True)
    delivery_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(price__gte=0, price__lte=999999.99), name='errand_price_bounds')]
        indexes = [models.Index(fields=['status', '-created_at'], name='errand_status_feed')]

    def __str__(self):
        return self.title

class task_event(models.Model):
    task = models.ForeignKey(task, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

class wallet_record(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    task = models.ForeignKey(task, on_delete=models.PROTECT)
    kind = models.CharField(max_length=20, choices=[('payment', '发布预付'), ('refund', '取消退款'), ('income', '完成收入')])
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['task', 'kind'], name='unique_task_wallet_action'),
            models.CheckConstraint(condition=models.Q(amount__gte=0, amount__lte=999999.99), name='wallet_record_amount_bounds'),
        ]

class question(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    task = models.ForeignKey(task, on_delete=models.PROTECT, null=True, blank=True)
    content = models.TextField(max_length=2000)
    status = models.CharField(max_length=20, default='pending', choices=[('pending', '等待管理员联系'), ('replied', '管理员已回复'), ('closed', '已解决')])
    reply_unread = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class question_reply(models.Model):
    question = models.ForeignKey(question, on_delete=models.PROTECT, related_name='replies')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    content = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
