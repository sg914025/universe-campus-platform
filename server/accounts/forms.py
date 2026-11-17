from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .models import Profile
from .regions import PROVINCES


class ProfileFields(forms.Form):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        # 暂时隐藏生源地字段，保留定义和已保存的数据，方便恢复。
        if not settings.ENABLE_HERITAGE:
            self.fields.pop('hometown_province',None)
            self.fields.pop('hometown_city',None)
    hometown_province = forms.ChoiceField(label='生源地省份',choices=[('','暂不填写'),*PROVINCES],required=False,help_text='选填，用于推荐家乡非遗；不会公开在论坛中。')
    hometown_city = forms.CharField(label='生源地城市',max_length=40,required=False,widget=forms.TextInput(attrs={'placeholder':'例如：贵阳，不填写详细地址'}))
    full_name = forms.CharField(label='姓名', max_length=50, widget=forms.TextInput(attrs={
        'placeholder': '请输入姓名', 'autocomplete': 'name',
    }))
    gender = forms.ChoiceField(label='性别', choices=[('', '请选择性别'), *Profile.Gender.choices])
    age = forms.IntegerField(label='年龄', min_value=0, max_value=120, required=False, help_text='选填，用于导诊对话中的年龄信息。', widget=forms.NumberInput(attrs={
        'placeholder': '请输入年龄（选填）', 'inputmode': 'numeric',
    }))


class RegistrationForm(UserCreationForm):
    hometown_province = ProfileFields.base_fields['hometown_province']
    hometown_city = ProfileFields.base_fields['hometown_city']
    full_name = ProfileFields.base_fields['full_name']
    gender = ProfileFields.base_fields['gender']
    age = ProfileFields.base_fields['age']
    username = forms.RegexField(label='账号', regex=r'^[A-Za-z][A-Za-z0-9_]{3,29}$', min_length=4, max_length=30,
        help_text='4–30 位，以字母开头，可含数字和下划线；大小写不区分。',
        error_messages={'invalid': '账号须以字母开头，仅包含字母、数字或下划线。'},
        widget=forms.TextInput(attrs={'placeholder': '设置你的登录账号', 'autocomplete': 'username', 'autocapitalize': 'none', 'spellcheck': 'false'}))

    class Meta(UserCreationForm.Meta):
        fields = ('full_name', 'gender', 'age','hometown_province','hometown_city', 'username', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.ENABLE_HERITAGE:
            self.fields.pop('hometown_province',None)
            self.fields.pop('hometown_city',None)
        self.fields['password1'].label = '密码'
        self.fields['password1'].help_text = '至少 8 位，不能是纯数字、常见密码或与账号过于相似。'
        self.fields['password1'].widget.attrs.update(placeholder='设置登录密码', autocomplete='new-password')
        self.fields['password2'].label = '确认密码'
        self.fields['password2'].help_text = ''
        self.fields['password2'].widget.attrs.update(placeholder='再次输入密码', autocomplete='new-password')

    def clean_username(self):
        username = self.cleaned_data['username'].lower()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('该账号已被注册，请更换账号或前往登录。')
        return username

    @transaction.atomic
    def save(self, commit=True):
        # Saving a registration always writes the user and required profile together.
        if not commit:
            raise ValueError('Registration must save user and profile atomically.')
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['full_name']
        user.save()
        Profile.objects.create(user=user, full_name=self.cleaned_data['full_name'],
            gender=self.cleaned_data['gender'], age=self.cleaned_data['age'],hometown_province=self.cleaned_data.get('hometown_province',''),hometown_city=self.cleaned_data.get('hometown_city',''))
        return user


class SignInForm(AuthenticationForm):
    error_messages = {
        'invalid_login': '学号或密码不正确。请确认学校已导入账号，并检查登录信息。',
        'inactive': '该账号暂不可用，请联系系统管理人员。',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = '学号'
        self.fields['username'].widget.attrs.update(placeholder='请输入学号', autocomplete='username', autocapitalize='none', spellcheck='false', inputmode='numeric')
        self.fields['password'].label = '密码'
        self.fields['password'].widget.attrs.update(placeholder='请输入密码', autocomplete='current-password')

    def clean_username(self):
        return self.cleaned_data['username'].lower()


class StudentCsvImportForm(forms.Form):
    csv_file = forms.FileField(label='新生名单 CSV', help_text='UTF-8 编码；必须包含“学号、姓名”，可选“性别、年龄”。')

    def clean_csv_file(self):
        upload = self.cleaned_data['csv_file']
        if not upload.name.lower().endswith('.csv'):
            raise forms.ValidationError('请选择 CSV 文件。')
        return upload


class StudentActivationForm(forms.Form):
    student_number = forms.CharField(label='学号', max_length=20, widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'username'}))
    full_name = forms.CharField(label='姓名', max_length=50, widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    new_password1 = forms.CharField(label='新密码', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    new_password2 = forms.CharField(label='确认新密码', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_student_number(self):
        value = self.cleaned_data['student_number'].strip()
        if value != self.user.username:
            raise forms.ValidationError('学号与激活卡不匹配。')
        return value

    def clean_full_name(self):
        value = self.cleaned_data['full_name'].strip()
        profile = getattr(self.user, 'guide_profile', None)
        if not profile or value != profile.full_name.strip():
            raise forms.ValidationError('姓名与学校导入的信息不匹配。')
        return value

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('new_password1')
        if password and password != cleaned.get('new_password2'):
            self.add_error('new_password2', '两次输入的密码不一致。')
        if password:
            try:
                validate_password(password, self.user)
            except forms.ValidationError as exc:
                self.add_error('new_password1', exc)
        return cleaned

    def save(self):
        self.user.set_password(self.cleaned_data['new_password1'])
        self.user.save(update_fields=['password'])
        Profile.objects.filter(user=self.user).update(must_change_password=False)
        return self.user


class FirstLoginPasswordChangeForm(PasswordChangeForm):
    student_number = forms.CharField(label='确认学号', max_length=20, widget=forms.TextInput(attrs={'inputmode': 'numeric'}))
    full_name = forms.CharField(label='确认姓名', max_length=50)

    field_order = ('student_number', 'full_name', 'old_password', 'new_password1', 'new_password2')

    def clean_student_number(self):
        value = self.cleaned_data['student_number'].strip()
        if value != self.user.username:
            raise forms.ValidationError('学号与当前账号不匹配。')
        return value

    def clean_full_name(self):
        value = self.cleaned_data['full_name'].strip()
        profile = getattr(self.user, 'guide_profile', None)
        if not profile or value != profile.full_name.strip():
            raise forms.ValidationError('姓名与学校导入的信息不匹配。')
        return value
