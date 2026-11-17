from django.conf import settings
from django.db import models

class tag(models.Model):
    name = models.CharField(max_length=32)
    slug = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '#' + self.name

categories = [('学习交流', '学习交流'), ('校园生活', '校园生活'), ('失物招领', '失物招领'), ('二手交易', '二手交易'), ('日常', '日常'), ('求助', '求助'), ('交友', '交友')]

class post(models.Model):
    image = models.ImageField(upload_to='posts/', blank=True)
    quoted_post = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='quotes')
    view_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    tags = models.ManyToManyField(tag, blank=True, related_name='posts')
    duplicate_key = models.CharField(max_length=64, blank=True, db_index=True)
    is_hidden = models.BooleanField(default=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    content = models.TextField(max_length=10000)
    category = models.CharField(max_length=20, choices=categories, default='校园生活')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['is_hidden', 'category', '-created_at'], name='post_category_feed')]

    def __str__(self):
        return self.title

class comment(models.Model):
    is_hidden = models.BooleanField(default=False)
    post = models.ForeignKey(post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

class profile(models.Model):
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    avatar = models.ImageField(upload_to='avatars/', blank=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nickname = models.CharField(max_length=30, blank=True)
    college = models.CharField(max_length=50, blank=True)
    major = models.CharField(max_length=50, blank=True)
    introduction = models.TextField(max_length=300, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(balance__gte=0, balance__lte=9999999999.99), name='wallet_balance_bounds')]

class history(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(post, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'post'], name='unique_history')]

class favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(post, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'post'], name='unique_favorite')]

class follow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following_rows')
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='follower_rows')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'target'], name='unique_follow')]

class chat_message(models.Model):
    is_hidden = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_chats')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_chats')
    content = models.CharField(max_length=2000, blank=True)
    shared_post = models.ForeignKey(post, on_delete=models.SET_NULL, null=True, blank=True)
    shared_title = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['receiver', 'is_read', 'is_hidden'], name='chat_inbox_unread'),
            models.Index(fields=['sender', 'receiver', 'created_at'], name='chat_conversation_time'),
        ]

class like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'post'], name='unique_like')]

class report(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports')
    post = models.ForeignKey(post, on_delete=models.SET_NULL, null=True, related_name='reports')
    title = models.CharField(max_length=100)
    content = models.TextField()
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=20, default='pending', choices=[('pending', '待审核'), ('kept', '保留帖子'), ('hidden', '下架帖子')])
    created_at = models.DateTimeField(auto_now_add=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_reports')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)

class recharge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default='pending', choices=[('pending', '等待管理员审核'), ('approved', '充值成功'), ('rejected', '审核未通过')])
    created_at = models.DateTimeField(auto_now_add=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_recharges')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)

class user_activity(models.Model):
    actions = [('post_view', '阅读帖子'), ('errand_open', '打开跑腿'), ('errand_create', '发布跑腿'), ('errand_take', '接单'), ('errand_complete', '完成订单'), ('post_like', '点赞'), ('post_favorite', '收藏')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=24, choices=actions)
    category = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

class risk_alert(models.Model):
    source_type = models.CharField(max_length=24)
    source_id = models.PositiveBigIntegerField()
    author_id = models.PositiveBigIntegerField(null=True, blank=True)
    author_name = models.CharField(max_length=150, blank=True)
    content = models.TextField(max_length=5000)
    reason = models.CharField(max_length=300)
    score = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, default='pending', choices=[('pending', '待人工复核'), ('cleared', '已确认正常'), ('hidden', '已隐藏')])
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_risks')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source_type', 'source_id'], name='unique_risk_source')]
        ordering = ['-created_at']

class announcement(models.Model):
    title = models.CharField(max_length=80)
    content = models.TextField(max_length=1000)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='campus_announcements')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return self.title
