from functools import wraps
from accounts.views import AUTH_MODULES
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET,require_POST,require_http_methods
from .models import DoctorProfile,Consultation,CaseConference,DiscussionMessage
from .doctor_forms import DoctorSignInForm,ReplyForm,DiscussionForm,ConferenceForm,MedicationReferenceForm
from .medication import medication_reference
from .interview import ANSWER_LABELS
from .parts import PARTS
from .drug_library import load_drugs,FIELD_LABELS
from .knowledge import load_knowledge
from .disease_aliases import DISEASE_ALIASES


def doctor_required(view):
    @wraps(view)
    def guarded(request,*args,**kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path(), reverse('management-login', args=['doctor']))
        doctor=DoctorProfile.objects.select_related('department').filter(user=request.user,active=True,department__active=True).first()
        if doctor is None:
            return HttpResponseForbidden('该账号没有医生权限。请使用患者登录或联系管理员。')
        request.doctor=doctor
        return view(request,*args,**kwargs)
    return never_cache(guarded)


def visible_consultations(doctor):
    return Consultation.objects.filter(Q(department=doctor.department)|Q(conferences__accepted_by=doctor,conferences__status='accepted')).distinct()


@never_cache
@sensitive_post_parameters()
@require_http_methods(['GET','POST'])
def sign_in(request):
    from campus.management_views import sign_in as management_sign_in
    from urllib.parse import urlencode
    if request.method == 'POST':
        return management_sign_in(request, 'doctor')
    target = reverse('management-login', args=['doctor'])
    if request.GET.get('next'):
        target += '?' + urlencode({'next': request.GET['next']})
    return redirect(target)


@doctor_required
@require_GET
def dashboard(request):
    records=visible_consultations(request.doctor).select_related('department','user','user__guide_profile')
    scope=request.GET.get('scope','own')
    if scope=='conference':
        records=records.exclude(department=request.doctor.department)
    else:
        scope='own';records=records.filter(department=request.doctor.department)
    if request.GET.get('status') in ('pending','replied'):
        records=records.filter(status=request.GET['status'])
    # 待接受的邀请只展示编号、发起科室和时间；不泄露患者资料与内部讨论。
    invitations=CaseConference.objects.filter(target_department=request.doctor.department,status='pending').select_related('requested_by__department','consultation')
    return render(request,'doctor/dashboard.html',{'doctor':request.doctor,'records':records[:100],'invitations':invitations,'scope':scope,'filter_status':request.GET.get('status',''),
                  'drug_count':len(load_drugs()['records']),'knowledge_count':len(load_knowledge()['records'])})


@doctor_required
@require_GET
def drug_library(request):
    data=load_drugs();records=data['records']
    categories=sorted({item['category'] for item in records})
    query=request.GET.get('q','')[:100].strip();category=request.GET.get('category','')
    if category:records=[item for item in records if item['category']==category]
    if query:records=[item for item in records if query.lower() in (item['name']+' '+item['english']).lower()]
    return render(request,'doctor/drug_library.html',{'doctor':request.doctor,'records':records,'categories':categories,'query':query,'category':category,
                  'count':len(data['records']),'matched':len(records),'data':data,'imported_at':parse_datetime(data.get('imported_at',''))})


@doctor_required
@require_GET
def drug_detail(request,drug_id):
    record=next((item for item in load_drugs()['records'] if item['id']==drug_id),None)
    if record is None:
        from django.http import Http404
        raise Http404
    return render(request,'doctor/drug_detail.html',{'doctor':request.doctor,'drug':record,
                  'sections':[{'label':FIELD_LABELS.get(key,key),'text':value} for key,value in record['excerpts'].items()]})


@doctor_required
@require_GET
def knowledge_library(request):
    data=load_knowledge();query=request.GET.get('q','')[:100].strip();kind=request.GET.get('kind','')
    records=data['records']
    if kind=='genetics':records=[item for item in records if item.get('kind')=='genetic_condition']
    elif kind=='health':records=[item for item in records if item.get('kind')!='genetic_condition']
    if query:
        mapped={title.lower() for word,titles in DISEASE_ALIASES.items() if query in word or word in query for title in titles}
        records=[item for item in records if query.lower() in (item['title']+' '+' '.join(item.get('synonyms',[]))).lower() or item['title'].lower() in mapped]
    from django.core.paginator import Paginator
    page=Paginator(records,20).get_page(request.GET.get('page'))
    return render(request,'doctor/knowledge.html',{'doctor':request.doctor,'page':page,'count':len(data['records']),'matched':len(records),'query':query,'kind':kind,'data':data})


@doctor_required
@require_GET
def case_detail(request,pk):
    record=get_object_or_404(visible_consultations(request.doctor).select_related('department','user','user__guide_profile','replied_by'),pk=pk)
    return render(request,'doctor/case.html',{
        'doctor':request.doctor,'record':record,'part_name':PARTS.get(record.part,{}).get('name',record.part),
        'answer_rows':[{'label':ANSWER_LABELS.get(key,key),'value':value} for key,value in record.followup_answers.items()],
        'reply_form':ReplyForm(initial={'content':record.doctor_reply}), 'discussion_form':DiscussionForm(),
        'conference_form':ConferenceForm(consultation=record),
        'medication_form':MedicationReferenceForm(initial=record.doctor_medication_reference.get('information',{})),
        'conferences':record.conferences.select_related('target_department','requested_by','accepted_by'),
        'discussion':record.discussion.select_related('doctor__department'),
        'can_manage_conference':record.department_id==request.doctor.department_id,
    })


@doctor_required
@require_POST
def generate_medication(request,pk):
    record=get_object_or_404(visible_consultations(request.doctor).select_related('user__guide_profile'),pk=pk)
    form=MedicationReferenceForm(request.POST)
    if not form.is_valid():
        messages.error(request,'请完整填写医生判断、过敏、正在用药和相关风险，并确认已核对；未生成用药建议。')
        return redirect('doctor-case',pk=pk)
    result=medication_reference(record,form.cleaned_data)
    result.update(information=form.cleaned_data,generated_at=timezone.now().isoformat(),generated_by=request.doctor.display_name)
    # 模型调用期间会诊可能被撤回；写入前再次检查访问权限。
    if not visible_consultations(request.doctor).filter(pk=pk).update(doctor_medication_reference=result):
        return HttpResponseForbidden('当前已无权访问这条咨询，用药参考未保存。')
    messages.success(request,'用药参考已整理，仅在医生工作台显示。')
    return redirect('doctor-case',pk=pk)


@doctor_required
@require_POST
def reply(request,pk):
    form=ReplyForm(request.POST)
    with transaction.atomic():
        record=get_object_or_404(visible_consultations(request.doctor).select_for_update(),pk=pk)
        if form.is_valid():
            record.doctor_reply=form.cleaned_data['content'].strip();record.replied_by=request.user
            record.replied_at=timezone.now();record.status='replied';record.reply_read=False
            record.save(update_fields=['doctor_reply','replied_by','replied_at','status','reply_read'])
            messages.success(request,'回复已发送到患者的站内信箱。')
        else:
            messages.error(request,'回复不能为空，最多 5000 字。')
    return redirect('doctor-case',pk=pk)


@doctor_required
@require_POST
def discuss(request,pk):
    form=DiscussionForm(request.POST)
    with transaction.atomic():
        record=get_object_or_404(visible_consultations(request.doctor).select_for_update(),pk=pk)
        if form.is_valid():
            DiscussionMessage.objects.create(consultation=record,doctor=request.doctor,content=form.cleaned_data['content'])
            messages.success(request,'内部讨论已添加。')
        else:
            messages.error(request,'讨论不能为空，最多 2000 字。')
    return redirect('doctor-case',pk=pk)


@doctor_required
@require_POST
def invite(request,pk):
    with transaction.atomic():
        record=get_object_or_404(visible_consultations(request.doctor).select_for_update(),pk=pk)
        if record.department_id != request.doctor.department_id:
            return HttpResponseForbidden('只有接诊科室医生可以申请或管理会诊。')
        form=ConferenceForm(request.POST,consultation=record)
        if form.is_valid():
            from campus.audit import record_event
            conference,created=CaseConference.objects.get_or_create(consultation=record,target_department=form.cleaned_data['department'],defaults={'requested_by':request.doctor,'reason':form.cleaned_data['reason']})
            old_status=conference.status
            reopened=not created and conference.status in ('declined','revoked')
            if reopened:
                conference.status='pending';conference.accepted_by=None;conference.requested_by=request.doctor;conference.reason=form.cleaned_data['reason']
                conference.save()
            if created or reopened:
                record_event(request.user,'doctor','申请会诊',conference,('status',),{'status':old_status} if reopened else {},{'status':'pending'})
            messages.success(request,'会诊邀请已发送，等待对方科室医生接受。')
        else:
            messages.error(request,'请选择有医生的其他科室，会诊原因须为 1–500 字。')
    return redirect('doctor-case',pk=pk)


@doctor_required
@require_POST
def respond_invitation(request,pk):
    with transaction.atomic():
        invitation=get_object_or_404(CaseConference.objects.select_for_update(),pk=pk,target_department=request.doctor.department,status='pending')
        action=request.POST.get('action')
        if action not in ('accept','decline'):
            return HttpResponseForbidden('无效操作。')
        invitation.status='accepted' if action=='accept' else 'declined'
        invitation.accepted_by=request.doctor if action=='accept' else None
        invitation.save(update_fields=['status','accepted_by'])
    if action=='accept':
        return redirect('doctor-case',pk=invitation.consultation_id)
    messages.success(request,'已拒绝本次邀请。')
    return redirect('doctor-dashboard')


@doctor_required
@require_POST
def revoke_invitation(request,pk):
    with transaction.atomic():
        invitation=get_object_or_404(CaseConference.objects.select_for_update(),pk=pk,consultation__department=request.doctor.department)
        invitation.status='revoked';invitation.save(update_fields=['status'])
    messages.success(request,'会诊已撤回，该受邀医生失去这条咨询的访问权限。')
    return redirect('doctor-case',pk=invitation.consultation_id)

from campus.audit import audit_change
reply=audit_change('doctor','triage.Consultation',('status','replied_at'),'回复导诊咨询')(reply)
respond_invitation=audit_change('doctor','triage.CaseConference',('status',),'处理会诊邀请')(respond_invitation)
revoke_invitation=audit_change('doctor','triage.CaseConference',('status',),'撤回会诊邀请')(revoke_invitation)
