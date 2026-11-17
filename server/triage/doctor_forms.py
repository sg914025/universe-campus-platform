from django import forms
from accounts.forms import SignInForm
from .models import DoctorProfile, Department


class DoctorSignInForm(SignInForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not DoctorProfile.objects.filter(user=user,active=True,department__active=True).exists():
            raise forms.ValidationError('该账号没有医生权限，请使用患者登录入口。',code='not_doctor')


class ReplyForm(forms.Form):
    content = forms.CharField(label='给患者的回复',max_length=5000,widget=forms.Textarea(attrs={'id':'doctor_reply_content','rows':5,'placeholder':'结合患者描述和 AI 初步推测，填写你的回复。'}))


class DiscussionForm(forms.Form):
    content = forms.CharField(label='内部会诊讨论',max_length=2000,widget=forms.Textarea(attrs={'id':'doctor_discussion_content','rows':3,'placeholder':'供参与医生讨论，不会发送到患者信箱。'}))


class MedicationReferenceForm(forms.Form):
    drug_choice = forms.ChoiceField(label='限定参考药品（选填）',required=False,choices=[('','按医生判断检索资料')])
    assessment = forms.CharField(label='医生当前判断',max_length=1000,widget=forms.Textarea(attrs={'rows':2,'placeholder':'例如：已评估为轻度关节疼痛，需要评估短期对症用药。'}))
    allergies = forms.CharField(label='已核对的药物过敏',max_length=300,widget=forms.TextInput(attrs={'placeholder':'写明药名及反应；无过敏请明确填写，未知填“不清楚”。'}))
    current_medicines = forms.CharField(label='目前正在用的药',max_length=500,widget=forms.TextInput(attrs={'placeholder':'包括处方药、非处方药；没有用药请明确填写。'}))
    risks = forms.CharField(label='相关用药风险',max_length=600,widget=forms.Textarea(attrs={'rows':2,'placeholder':'请核对肝肾、消化道出血、心血管、饮酒、妊娠/哺乳等情况；未知请注明。'}))
    confirmed = forms.BooleanField(label='我已核对上述信息，将结合诊断和实际药品说明书决定是否用药。')

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from .drug_library import load_drugs
        self.fields['drug_choice'].choices=[('','按医生判断检索资料')]+[(item['id'],item['name']+' · '+item['category']) for item in load_drugs()['records']]


class ConferenceForm(forms.Form):
    department = forms.ModelChoiceField(label='邀请科室',queryset=Department.objects.none(),empty_label='请选择科室')
    reason = forms.CharField(label='会诊原因',max_length=500,widget=forms.Textarea(attrs={'rows':3,'placeholder':'简单说明需要其他科室确认什么。接受邀请后可查看完整资料。'}))

    def __init__(self,*args,consultation,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['department'].queryset=Department.objects.filter(active=True,doctors__active=True,doctors__user__is_active=True).exclude(pk=consultation.department_id).distinct()
