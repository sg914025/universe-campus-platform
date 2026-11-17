import json
import uuid
import hashlib

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from django.core.cache import cache

from accounts.models import Profile
from .models import Consultation, Department
from .parts import PARTS, assess_description
from .interview import interview_step, validate_answers
from .ollama_client import model_status
from .knowledge import load_knowledge
from .reporting import create_report
from .drug_library import load_drugs
from .report_translation import remember_preview


def access_error(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': '请先登录。'}, status=401)
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None or not profile.is_complete:
        return JsonResponse({'error': '请先完善个人资料。'}, status=403)
    return None


@never_cache
@require_POST
def assess(request):
    error = access_error(request)
    if error is not None:
        return error
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': '提交格式不正确。'}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({'error': '提交格式不正确。'}, status=400)
    if data.get('accepted_notice') is not True:
        return JsonResponse({'error': '请先阅读高级导诊免责声明。'}, status=400)
    if 'preview' in data and not isinstance(data['preview'], bool):
        return JsonResponse({'error': '提交内容不正确。'}, status=400)
    for key in ('part', 'detail', 'description', 'duration', 'feeling', 'request_key'):
        if not isinstance(data.get(key, ''), str):
            return JsonResponse({'error': '提交内容不正确。'}, status=400)
    part = data.get('part', '')
    detail = data.get('detail', '').strip()
    description = data.get('description', '').strip()
    duration = data.get('duration', '').strip()
    feeling = data.get('feeling', 'mild')
    if part not in PARTS or detail and detail not in PARTS[part]['details']:
        return JsonResponse({'error': '请先选择正确的身体部位。'}, status=400)
    if not 1 <= len(description) <= 2000 or len(duration) > 60:
        return JsonResponse({'error': '请填写症状描述（最多 2000 字），持续时间最多 60 字。'}, status=400)
    if feeling not in ('mild', 'moderate', 'severe'):
        return JsonResponse({'error': '请选择不适程度。'}, status=400)
    try:
        request_key = uuid.UUID(data.get('request_key', ''))
    except ValueError:
        return JsonResponse({'error': '提交标识不正确，请重新打开页面。'}, status=400)
    try:
        followup_answers = validate_answers(data.get('answers', {}))
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    severity = followup_answers.get('severity', '')
    if severity == '很明显，想请医生确认':
        feeling = 'severe'
    elif severity == '活动或睡眠受到影响' and feeling != 'severe':
        feeling = 'moderate'
    level, emergency = assess_description(description + ' ' + ' '.join(followup_answers.values()), feeling)
    consultation = Consultation.objects.filter(user=request.user,request_key=request_key).first()
    if consultation is None:
        # Keep the first analysis private on the server while the patient chooses
        # a care channel. Never trust a report returned by the browser.
        fingerprint = json.dumps([part, detail, description, duration, followup_answers, emergency,
                                  request.user.guide_profile.age], sort_keys=True, ensure_ascii=False)
        cache_key = f'triage-preview:{request.user.pk}:{request_key}:' + hashlib.sha256(fingerprint.encode()).hexdigest()
        report = cache.get(cache_key)
        if report is None:
            report = create_report(part, detail, description, duration, followup_answers, emergency, request.user.guide_profile.age)
            cache.set(cache_key, report, 900)
        department = Department.objects.filter(slug=report['department'],active=True).first()
        if department is None:
            department = Department.objects.get(slug='general')
            report.update(department='general',department_name=department.name,routing_reason='建议科室暂不可用，转交全科医学科核实。')
        if data.get('preview') is True:
            remember_preview(request.user.pk,request_key,report)
            return JsonResponse({'level': level, 'emergency': emergency, 'queued': False,
                'report': report, 'department': department.name,
                'message': '导诊信息已整理，请选择线上咨询或到诊室就诊。',
                'urgent_message': '紧急情况请立即寻求现场急救帮助，不要等待线上回复。' if emergency else ''})
        consultation, created = Consultation.objects.get_or_create(user=request.user, request_key=request_key,
            defaults={'part':part,'detail':detail,'description':description,'duration':duration,'followup_answers':followup_answers,
                      'feeling':feeling,'level':level,'emergency':emergency,'department':department,'ai_report':report})
    remember_preview(request.user.pk,request_key,consultation.ai_report)
    result = {'level':consultation.level,'emergency':consultation.emergency,'queued':True,
              'code':consultation.code,'status':consultation.get_status_display(),'report':consultation.ai_report,
              'department':consultation.department.name if consultation.department else '待分诊',
              'message':'已自动分诊到对应科室医生待答列表。医生回复后，请留意站内信箱。'}
    emergency = consultation.emergency
    if emergency:
        result['urgent_message'] = '描述涉及紧急提示词。若这些表现正在发生，请及时拨打 120 或寻求急诊帮助，不要等待信箱回复。'
    return JsonResponse(result)


@never_cache
@require_GET
def inbox(request):
    error = access_error(request)
    if error is not None:
        return error
    records = Consultation.objects.filter(user=request.user).select_related('replied_by','department')
    messages = [{'id': record.pk, 'code': record.code, 'part': PARTS.get(record.part, {}).get('name', record.part),
                 'detail': record.detail, 'description': record.description, 'answers': record.followup_answers,
                 'department':record.department.name if record.department else '待分诊','report':record.ai_report,
                 'status': record.status, 'status_label': record.get_status_display(),
                 'reply': record.doctor_reply, 'reply_read': record.reply_read,
                 'doctor': (record.replied_by.get_full_name() or record.replied_by.username) if record.replied_by else '',
                 'created_at': record.created_at.isoformat(),
                 'replied_at': record.replied_at.isoformat() if record.replied_at else None}
                for record in records[:50]]
    unread = records.filter(status='replied', reply_read=False).count()
    return JsonResponse({'messages': messages, 'unread': unread})


@never_cache
@require_POST
def read_reply(request, pk):
    error = access_error(request)
    if error is not None:
        return error
    record = get_object_or_404(Consultation, pk=pk, user=request.user)
    if record.status == 'replied':
        record.reply_read = True
        record.save(update_fields=['reply_read'])
    return JsonResponse({'ok': True})


@never_cache
@require_GET
def ai_status(request):
    error = access_error(request)
    if error is not None:
        return error
    knowledge=load_knowledge()
    return JsonResponse({**model_status(), 'knowledge_count': len(knowledge['records']),
                         'health_topics':knowledge['health_topics'],'genetic_conditions':knowledge['genetic_conditions'],
                         'drug_count':len(load_drugs()['records'])})


@never_cache
@require_POST
def followup(request):
    error = access_error(request)
    if error is not None:
        return error
    if len(request.body) > 16000:
        return JsonResponse({'error': '描述过长。'}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or data.get('accepted_notice') is not True:
            raise ValueError('请先阅读免责声明。')
        for key in ('part', 'detail', 'description', 'duration', 'feeling'):
            if not isinstance(data.get(key, ''), str):
                raise ValueError('提交内容不正确。')
        part, detail = data.get('part', ''), data.get('detail', '')
        description, duration, feeling = data.get('description', '').strip(), data.get('duration', '').strip(), data.get('feeling', 'mild')
        if part not in PARTS or detail and detail not in PARTS[part]['details']:
            raise ValueError('请选择正确的身体部位。')
        if not 1 <= len(description) <= 2000 or len(duration) > 60 or feeling not in ('mild', 'moderate', 'severe'):
            raise ValueError('请检查描述、持续时间和不适程度。')
        answers = validate_answers(data.get('answers', {}))
    except (ValueError, UnicodeDecodeError) as error:
        return JsonResponse({'error': str(error) or '提交格式不正确。'}, status=400)
    return JsonResponse(interview_step(part, detail, description, duration, feeling, answers))
