from django import forms
from decimal import Decimal
import re
from .models import post, comment, profile, announcement
from campus.content_policy import PublicationPolicyMixin

class hashtag_field(forms.CharField):
    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return []
        result = []
        seen = set()
        for raw in re.split(r'[\s,，]+', value.strip()):
            name = raw.lstrip('#').strip()
            if not name:
                continue
            if len(name) > 24 or not re.fullmatch(r'[\w-]+', name, flags=re.UNICODE):
                raise forms.ValidationError('标签只支持文字、数字、下划线和短横线，最多 24 个字符')
            key = name.casefold()
            if key not in seen:
                result.append(name)
                seen.add(key)
        if len(result) > 10:
            raise forms.ValidationError('每个帖子最多添加 10 个标签')
        return result

class post_form(PublicationPolicyMixin,forms.ModelForm):
    policy_fields=('title','content','tags_text')
    tags_text = hashtag_field(label='话题标签', required=False, max_length=400, help_text='可写 #求助 #校园生活，新标签会自动加入标签库。')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = post.objects.filter(is_hidden=False).order_by('-created_at')
        if self.instance.pk:
            choices = choices.exclude(pk=self.instance.pk)
        self.fields['quoted_post'].queryset = choices
        self.fields['quoted_post'].empty_label = '不引用帖子'
        if self.instance.pk:
            self.fields['tags_text'].initial = ' '.join('#' + item.name for item in self.instance.tags.all())
        self.order_fields(['title', 'category', 'content', 'image', 'quoted_post', 'tags_text'])

    class Meta:
        model = post
        fields = ['title', 'category', 'content', 'image', 'quoted_post']
        labels = {'title': '标题', 'category': '分类', 'content': '正文', 'image': '上传图片', 'quoted_post': '引用帖子（可选）'}
        widgets = {'content': forms.Textarea(attrs={'rows': 9})}

class comment_form(PublicationPolicyMixin,forms.ModelForm):
    policy_fields=('content',)
    class Meta:
        model = comment
        fields = ['content']
        labels = {'content': '写下你的评论'}
        widgets = {'content': forms.Textarea(attrs={'rows': 3})}

class profile_form(forms.ModelForm):
    class Meta:
        model = profile
        fields = ['avatar', 'nickname', 'college', 'major', 'introduction']
        labels = {'avatar': '头像', 'nickname': '昵称', 'college': '学院', 'major': '专业', 'introduction': '个人简介'}
        widgets = {'introduction': forms.Textarea(attrs={'rows': 4})}

class recharge_form(forms.Form):
    code = forms.CharField(label='充值代码', max_length=100, widget=forms.TextInput(attrs={'placeholder': '请输入充值代码'}))

class recharge_review_form(forms.Form):
    action = forms.ChoiceField(choices=[('approve', '通过'), ('reject', '拒绝')])
    amount = forms.DecimalField(label='充值金额', min_value=Decimal('0.01'), max_value=Decimal('99999999.99'), max_digits=10, decimal_places=2, required=False)
    note = forms.CharField(label='审核备注', max_length=500, required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def clean(self):
        data = super().clean()
        if data.get('action') == 'approve' and data.get('amount') is None:
            self.add_error('amount', '审核通过时请填写充值金额')
        return data

class announcement_form(forms.ModelForm):
    class Meta:
        model = announcement
        fields = ['title', 'content']
        labels = {'title': '公告标题', 'content': '公告内容'}
        widgets = {'content': forms.Textarea(attrs={'rows': 4, 'placeholder': '输入要置顶在校园广场的通知内容'})}
