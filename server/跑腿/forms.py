from decimal import Decimal
from django import forms
from .models import task
from campus.content_policy import PublicationPolicyMixin

class task_form(PublicationPolicyMixin,forms.ModelForm):
    policy_fields=('title','description','address')
    price = forms.DecimalField(label='跑腿价格（元）', min_value=Decimal('0.01'), max_value=Decimal('999999.99'), max_digits=8, decimal_places=2)

    class Meta:
        model = task
        fields = ['title', 'category', 'description', 'address', 'phone', 'price']
        labels = {'title': '订单标题', 'category': '跑腿类型', 'description': '任务说明（公开）', 'address': '详细地址（接单后可见）', 'phone': '手机号（接单后可见）'}
        widgets = {'description': forms.Textarea(attrs={'rows': 4}), 'address': forms.TextInput(attrs={'placeholder': '取件地点及送达地址'}), 'phone': forms.TextInput(attrs={'inputmode': 'tel'})}

    def clean_phone(self):
        value = self.cleaned_data['phone'].strip()
        if not value.isdecimal() or len(value) != 11 or not value.startswith('1'):
            raise forms.ValidationError('请输入 11 位手机号')
        return value

class delivery_form(forms.ModelForm):
    proof = forms.ImageField(label='送达照片', required=True)

    class Meta:
        model = task
        fields = ['proof', 'delivery_note']
        labels = {'delivery_note': '送达说明（可选）'}
        widgets = {'delivery_note': forms.Textarea(attrs={'rows': 3})}

    def clean_proof(self):
        image = self.cleaned_data['proof']
        if image.size > 8 * 1024 * 1024:
            raise forms.ValidationError('照片最大 8 mb')
        if image.image.format not in ['JPEG', 'PNG', 'WEBP']:
            raise forms.ValidationError('请上传 jpg、png 或 webp 照片')
        return image

class question_form(forms.Form):
    content = forms.CharField(label='你的问题', max_length=2000, widget=forms.Textarea(attrs={'rows': 5, 'placeholder': '描述问题，管理员会在这里联系你。'}))
