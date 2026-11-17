from functools import wraps
from urllib.parse import urlencode, urlsplit

from django import forms
from django.contrib.auth import login, logout
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from accounts.forms import SignInForm
from triage.models import DoctorProfile

ROLES = {
    'doctor': {'title': '医生登录', 'description': '查看本科室咨询、核实 AI 整理结果并参与会诊。', 'symbol': '✚', 'destination': '/doctor/', 'prefixes': ('/doctor/',), 'color': '#18786b'},
    'campus': {'title': '论坛 / 跑腿管理员', 'description': '审核论坛内容、处理跑腿订单与用户咨询。', 'symbol': '☏', 'destination': '/campus-admin/', 'prefixes': ('/campus-admin/',), 'color': '#9a6336'},
    'booking': {'title': '预约管理员', 'description': '维护校园场地、开放状态并查看预约记录。', 'symbol': '▦', 'destination': '/campus-admin/bookings/', 'prefixes': ('/campus-admin/bookings/', '/campus-admin/venues/', '/campus-admin/waitlist/'), 'color': '#75618f'},
    'superadmin': {'title': '总管理员', 'description': '创建医生、论坛 / 跑腿管理员和预约管理员账号，分配对应权限。', 'symbol': '⊙', 'destination': '/management/overview/', 'prefixes': ('/management/accounts/', '/management/overview/', '/management/audit/', '/management/security/'), 'color': '#36566b'},
}


def has_role(user, role):
    if not user.is_authenticated or not user.is_active:
        return False
    if role == 'superadmin':
        return user.is_superuser
    if role == 'doctor':
        return DoctorProfile.objects.filter(user=user, active=True, department__active=True).exists()
    return user.has_perm('campus.manage_bookings' if role == 'booking' else 'campus.manage_campus')


def destination(request, role):
    fallback = ROLES[role]['destination']
    value = request.POST.get('next') or request.GET.get('next') or fallback
    if not url_has_allowed_host_and_scheme(value, {request.get_host()}, require_https=request.is_secure()):
        return fallback
    # Only return to a workspace owned by the selected role. Never loop into a login page.
    path = urlsplit(value).path
    if path.startswith(('/doctor/login/', '/management/login/', '/management/logout/')):
        return fallback
    if role == 'campus' and path.startswith(ROLES['booking']['prefixes']):
        return fallback
    return value if path.startswith(ROLES[role]['prefixes']) else fallback


class ManagementSignInForm(SignInForm):
    def __init__(self, *args, role, **kwargs):
        self.role = role
        super().__init__(*args, **kwargs)
        self.fields['username'].label = '账号'
        self.fields['username'].widget.attrs['placeholder'] = '请输入账号'
        from .ui_language import translate
        code = self.request.session.get('campus_language', self.request.COOKIES.get('campus_language', 'zh')) if self.request else 'zh'
        for field in self.fields.values():
            if 'placeholder' in field.widget.attrs:
                field.widget.attrs['placeholder'] = translate(field.widget.attrs['placeholder'], code)

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not has_role(user, self.role):
            raise forms.ValidationError('该账号没有所选后台的权限，请选择正确身份或联系系统管理员。', code='wrong_role')


@never_cache
@require_GET
def portal(request):
    roles = [dict(meta, key=key, allowed=has_role(request.user, key)) for key, meta in ROLES.items()]
    return render(request, 'campus/management/portal.html', {'roles': roles})


@never_cache
@sensitive_post_parameters()
@require_http_methods(['GET', 'POST'])
def sign_in(request, role):
    if role not in ROLES:
        raise Http404
    if request.method == 'GET' and has_role(request.user, role):
        return redirect(destination(request, role))
    form = ManagementSignInForm(request, data=request.POST if request.method == 'POST' else None, role=role)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect(destination(request, role))
    return render(request, 'campus/management/login.html', {'form': form, 'role': role, 'meta': ROLES[role], 'next_url': destination(request, role)})


def role_required(role):
    def decorate(view):
        @wraps(view)
        def guarded(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), reverse('management-login', args=[role]))
            if not has_role(request.user, role):
                from .ui_language import translate
                return HttpResponseForbidden(translate('该账号没有所选后台的权限，请选择正确身份或联系系统管理员。', request.session.get('campus_language', 'zh')))
            return view(request, *args, **kwargs)
        return never_cache(guarded)
    return decorate


@never_cache
@require_POST
def sign_out(request):
    logout(request)
    return redirect('management')


@never_cache
@require_POST
def language(request):
    from .ui_language import LANGUAGES
    code = request.POST.get('language')
    if code not in LANGUAGES:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest('Unsupported language')
    value = request.POST.get('next', '/')
    if not url_has_allowed_host_and_scheme(value, {request.get_host()}, require_https=request.is_secure()):
        value = '/'
    request.session['campus_language'] = code
    response = redirect(value)
    response.set_cookie('campus_language', code, max_age=31536000, httponly=True, samesite='Lax', secure=request.is_secure())
    return response


@role_required('superadmin')
@sensitive_post_parameters()
@require_http_methods(['GET', 'POST'])
def accounts(request):
    from django.contrib import messages
    from django.contrib.auth.models import User
    from django.core.paginator import Paginator
    from django.db import IntegrityError, transaction
    from .audit import record_event
    from django.db.models import Q
    from .staff_forms import StaffCreationForm
    from accounts.forms import StudentCsvImportForm
    from accounts.models import Profile, StudentImportBatch
    from accounts.student_import import StudentImportError, parse_student_csv
    action = (request.POST.get('action') or ('preview_students' if request.FILES else 'create_staff')) if request.method == 'POST' else ''
    form = StaffCreationForm(request.POST if action == 'create_staff' else None)
    import_form = StudentCsvImportForm(request.POST if action == 'preview_students' else None,
                                       request.FILES if action == 'preview_students' else None)
    if action == 'create_staff' and form.is_valid():
        try:
            with transaction.atomic():
                created_user=form.save()
                record_event(request.user,"superadmin","创建管理账号",created_user)
        except IntegrityError:
            form.add_error('username', '该账号已存在，请更换账号。')
        else:
            messages.success(request, '管理账号已创建，可从对应身份入口登录。')
            return redirect('management-accounts')
    elif action == 'preview_students' and import_form.is_valid():
        try:
            rows = parse_student_csv(import_form.cleaned_data['csv_file'])
        except StudentImportError as exc:
            import_form.add_error('csv_file', str(exc))
        else:
            existing = set(User.objects.filter(username__in=[row['student_number'] for row in rows]).values_list('username', flat=True))
            for row in rows:
                row['existing'] = row['student_number'] in existing
            batch = StudentImportBatch.objects.create(created_by=request.user,
                original_filename=import_form.cleaned_data['csv_file'].name[:255], preview_rows=rows,
                total_count=len(rows), skipped_count=len(existing.intersection({row['student_number'] for row in rows})))
            return redirect(reverse('management-accounts') + '?preview=' + str(batch.pk))
    users = User.objects.filter(Q(doctor_profile__isnull=False) | Q(is_superuser=True) |
        Q(user_permissions__content_type__app_label='campus', user_permissions__codename__in=['manage_campus', 'manage_bookings']) |
        Q(groups__permissions__content_type__app_label='campus', groups__permissions__codename__in=['manage_campus', 'manage_bookings'])).distinct().order_by('-date_joined')
    page = Paginator(users, 20).get_page(request.GET.get('page'))
    for user in page:
        user.workspace_roles = ['医生' if key == 'doctor' else meta['title'] for key, meta in ROLES.items() if has_role(user, key)]
        doctor = DoctorProfile.objects.select_related('department').filter(user=user).first()
        user.staff_department = doctor.department.name if doctor else ''
    students = User.objects.select_related('guide_profile', 'guide_profile__import_batch').filter(
        guide_profile__student_number__gt='', is_staff=False, is_superuser=False)
    query = request.GET.get('q', '').strip()
    state = request.GET.get('student_state', '')
    activation = request.GET.get('activation', '')
    if query:
        students = students.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(guide_profile__full_name__icontains=query))
    if state in ('active', 'inactive'):
        students = students.filter(is_active=(state == 'active'))
    if activation in ('pending', 'complete'):
        students = students.filter(guide_profile__must_change_password=(activation == 'pending'))
    student_page = Paginator(students.order_by('-date_joined'), 30).get_page(request.GET.get('student_page'))
    preview = StudentImportBatch.objects.filter(pk=request.GET.get('preview'), status='preview').first() if request.GET.get('preview', '').isdigit() else None
    batches = StudentImportBatch.objects.select_related('created_by')[:12]
    return render(request, 'campus/management/accounts.html', {'form': form, 'import_form': import_form,
        'page': page, 'student_page': student_page, 'query': query, 'student_state': state,
        'activation': activation, 'preview_batch': preview, 'batches': batches})


@role_required('superadmin')
@require_POST
def confirm_student_import(request, pk):
    from django.contrib import messages
    from accounts.student_import import confirm_batch,StudentImportBusy,StudentImportError
    try:batch,created,skipped,repeated=confirm_batch(pk,request.user)
    except StudentImportBusy as error:
        messages.error(request,str(error));return redirect(reverse('management-accounts')+'?preview='+str(pk))
    except StudentImportError as error:
        messages.error(request,str(error));return redirect('management-accounts')
    if repeated:
        messages.info(request,'该批次已完成导入，没有重复创建账号或修改密码。');return redirect('management-accounts')
    request.session['student_activation_ids']=[user.pk for user in created]
    messages.success(request,f'学生账号导入完成：新建 {len(created)} 个，跳过已有 {skipped} 个。')
    return redirect(reverse('student-activation-cards')+'?batch='+str(batch.pk)) if created else redirect('management-accounts')


@role_required('superadmin')
@require_POST
def rollback_student_import(request, pk):
    from django.contrib import messages
    from django.contrib.auth.models import User
    from django.db import transaction
    from django.utils import timezone
    from accounts.models import StudentImportBatch
    from .audit import record_event
    with transaction.atomic():
        batch = StudentImportBatch.objects.select_for_update().filter(pk=pk, status='imported').first()
        if not batch:
            raise Http404
        students = User.objects.filter(guide_profile__import_batch=batch)
        count = students.filter(is_active=True).update(is_active=False)
        batch.status = 'rolled_back'; batch.rolled_back_at = timezone.now()
        batch.save(update_fields=['status', 'rolled_back_at'])
        record_event(request.user, 'superadmin', '撤销学生导入批次', batch)
    messages.success(request, f'导入批次已撤销，已停用 {count} 个学生账号；业务数据和账号记录均已保留。')
    return redirect('management-accounts')


@role_required('superadmin')
@sensitive_post_parameters()
@require_POST
def student_account_action(request, pk):
    from django.contrib import messages
    from django.contrib.auth.models import User
    from django.db import transaction
    from accounts.models import Profile
    from .audit import record_event
    action = request.POST.get('student_action')
    if action not in ('activate', 'deactivate', 'reset_password'):
        raise Http404
    with transaction.atomic():
        student = User.objects.select_for_update().filter(pk=pk, is_staff=False, is_superuser=False,
            guide_profile__student_number__gt='').first()
        if not student:
            raise Http404
        if action == 'activate':
            student.is_active = True; student.save(update_fields=['is_active']); message = '学生账号已启用。'
        elif action == 'deactivate':
            student.is_active = False; student.save(update_fields=['is_active']); message = '学生账号已停用。'
        else:
            student.set_password(student.username); student.save(update_fields=['password'])
            Profile.objects.filter(user=student).update(must_change_password=True)
            message = '密码已重置为学号，学生下次登录必须核对身份并修改密码。'
        record_event(request.user, 'superadmin', {'activate':'启用学生账号','deactivate':'停用学生账号','reset_password':'重置学生密码'}[action], student)
    messages.success(request, message)
    return redirect('management-accounts')


@role_required('superadmin')
@require_GET
def student_csv_template(request):
    content = '\ufeff学号,姓名,性别,年龄\n20260001,张三,男,18\n20260002,李四,女,19\n'
    response = HttpResponse(content, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="student-import-template.csv"'
    return response


@role_required('superadmin')
@require_GET
def student_activation_cards(request):
    from django.contrib.auth.models import User
    batch_id = request.GET.get('batch', '')
    students_query = User.objects.select_related('guide_profile').filter(guide_profile__must_change_password=True)
    if batch_id.isdigit():
        students_query = students_query.filter(guide_profile__import_batch_id=batch_id)
    else:
        students_query = students_query.filter(pk__in=request.session.get('student_activation_ids', []))
    students = list(students_query.order_by('username'))
    for student in students:
        student.masked_number = '••••' + student.username[-4:]
    return render(request, 'campus/management/activation_cards.html', {'students': students})


@role_required('superadmin')
@require_GET
def student_activation_qr(request, pk):
    from io import BytesIO
    import qrcode
    from django.contrib.auth.models import User
    from django.shortcuts import get_object_or_404
    from accounts.activation import token_for
    student = get_object_or_404(User.objects.select_related('guide_profile'), pk=pk,
                                guide_profile__must_change_password=True, is_active=True)
    url = request.build_absolute_uri(reverse('student-activate', args=[token_for(student)]))
    output = BytesIO()
    qrcode.make(url).save(output, format='PNG')
    response = HttpResponse(output.getvalue(), content_type='image/png')
    response['Cache-Control'] = 'private, no-store'
    return response
