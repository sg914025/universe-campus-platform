from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Permission, User
from django.db import transaction
from accounts.forms import RegistrationForm
from triage.models import Department, DoctorProfile


class StaffCreationForm(UserCreationForm):
    username = RegistrationForm.base_fields['username']
    full_name = forms.CharField(label='姓名', max_length=50)
    role = forms.ChoiceField(label='管理身份', choices=[('doctor', '医生'), ('campus', '论坛 / 跑腿管理员'), ('booking', '预约管理员')])
    department = forms.ModelChoiceField(label='所属科室', queryset=Department.objects.none(), required=False, empty_label='请选择科室', help_text='创建医生时必须选择科室；其他管理员无需选择。')

    class Meta(UserCreationForm.Meta):
        fields = ('username', 'full_name', 'role', 'department', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.filter(active=True).order_by('name')
        self.fields['password1'].label = '密码'
        self.fields['password2'].label = '确认密码'
        self.order_fields(self.Meta.fields)

    def clean_username(self):
        value = self.cleaned_data['username'].lower()
        if User.objects.filter(username__iexact=value).exists():
            raise forms.ValidationError('该账号已存在，请更换账号。')
        return value

    def clean(self):
        data = super().clean()
        if data.get('role') == 'doctor' and not data.get('department'):
            self.add_error('department', '创建医生账号必须选择科室。')
        if data.get('role') != 'doctor':
            data['department'] = None
        return data

    @transaction.atomic
    def save(self, commit=True):
        if not commit:
            raise ValueError('Staff creation must be atomic.')
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['full_name']
        user.is_staff = False
        user.is_superuser = False
        user.save()
        role = self.cleaned_data['role']
        if role == 'doctor':
            DoctorProfile.objects.create(user=user, display_name=self.cleaned_data['full_name'], department=self.cleaned_data['department'], active=True)
        else:
            permission = Permission.objects.get(content_type__app_label='campus', codename='manage_bookings' if role == 'booking' else 'manage_campus')
            user.user_permissions.add(permission)
        return user
