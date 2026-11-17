from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.core import signing
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from .forms import FirstLoginPasswordChangeForm, ProfileFields, SignInForm, StudentActivationForm
from .models import Profile
from triage.parts import PARTS
from triage.models import Consultation, DoctorProfile


AUTH_MODULES = {
    'campus': {'name':'校园账号','destination':'/','color':'#426b53','wash':'#edf3e5','icon':'✳','heading':'校园生活，','highlight':'从这里连接。','description':'分享日常，找到帮手，照顾健康，安排时光。','tag_one':'一个账号，四种校园体验','tag_two':'选一个入口，开始今天','step_two':'选择校园服务','step_three':'开始校园日常','footer':'校园广场、跑腿、AI 导诊和场地预约共用一个账号。','disclosure':'姓名、性别和账号资料用于本系统账号识别与资料管理，密码以哈希形式保存。各模块按照对应功能保存使用记录。'},
    'forum': {'name':'校园广场','destination':'/forum/','color':'#64783f','wash':'#f0f3e5','icon':'☏','heading':'遇见同学，','highlight':'聊聊新鲜事。','description':'分享日常、交流学习，也发现校园里的同好。','tag_one':'分享你的校园日常','tag_two':'让有趣的想法被看见','step_two':'发现校园动态','step_three':'发帖与交流','footer':'交流时尊重同学，请勿公开他人的联系方式或个人隐私。','disclosure':'账号资料用于本系统身份识别。发帖、评论及校园昵称会按论坛功能展示，请避免公开私人信息。密码以哈希形式保存。'},
    'errands': {'name':'校园跑腿','destination':'/errands/','color':'#b9682f','wash':'#fbefdd','icon':'↗','heading':'顺路帮个忙，','highlight':'让小事更轻松。','description':'取快递、代买、送东西，把需求交给顺路的同学。','tag_one':'发布需求，等待同学接单','tag_two':'送达确认，完成互助','step_two':'发布或接取任务','step_three':'送达并确认','footer':'接单前核对任务要求；送达后确认订单，详细地址与手机号按订单权限展示。','disclosure':'账号用于订单识别。任务、地址和联系方式按跑腿功能保存，详细地址及手机号仅向有权限的订单参与者展示。密码以哈希形式保存。'},
    'guide': {'name':'AI 导诊','destination':'/guide/','color':'#18786b','wash':'#e7f3ee','icon':'＋','heading':'说说不舒服，','highlight':'一起梳理方向。','description':'描述症状与既往病史，逐步了解可能的就诊方向。','tag_one':'从你的描述开始','tag_two':'AI 整理，医生核实','step_two':'描述你的症状','step_three':'了解就诊方向','footer':'简单导诊为规则演示，高级导诊可使用本地 AI 追问；均不能代替医生诊断。','disclosure':'姓名、性别和账号资料用于账号识别与资料管理，密码以哈希形式保存。简单导诊内容不保存；高级导诊提交后台的内容用于医护回复并保存在数据库。'},
    'booking': {'name':'场地预约','destination':'/booking/','color':'#626fa7','wash':'#edf0fa','icon':'▦','heading':'留一个位置，','highlight':'安排你的好时光。','description':'预约自习室座位和运动场地，让学习与运动各有时间。','tag_one':'选择场地与空闲时段','tag_two':'我的预约，一目了然','step_two':'选择场地与时间','step_three':'确认并查看预约','footer':'预约记录保存在本系统，目前尚未对接学校预约系统，请以学校实际安排为准。','disclosure':'账号用于预约身份识别，场地、日期、时段和预约状态保存在本系统。个人预约页面只显示本人的记录，管理人员可管理场地预约。密码以哈希形式保存。'},
}

def auth_module(request, module=None):
    if module in AUTH_MODULES:
        return module
    destination=next_destination(request)
    from urllib.parse import urlsplit
    path=urlsplit(destination).path
    for key in ('forum','errands','guide','booking'):
        prefix=AUTH_MODULES[key]['destination']
        if path == prefix.rstrip('/') or path.startswith(prefix):
            return key
    return 'campus'

def next_destination(request, module=None):
    value = request.POST.get('next') or request.GET.get('next') or AUTH_MODULES.get(module,AUTH_MODULES['campus'])['destination']
    if url_has_allowed_host_and_scheme(value, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return value
    return reverse('home')


def auth_page(request, form, mode, module=None, **context):
    meta = {
        'register': ('首次使用，先创建你的账号', '填写基本信息后，即可进入校园生活站。', '注册并进入校园'),
        'login': ('欢迎回来', '登录你的账号，继续校园生活。', '登录并进入校园'),
        'profile': ('完善个人资料', '姓名和性别为必填，完成后才能使用导诊。', '保存资料并进入导诊'),
        'password': ('修改登录密码', '首次登录请设置仅你本人知道的新密码。', '保存新密码'),
    }
    title, subtitle, action = meta[mode]
    module=auth_module(request,module) if mode not in ('profile','password','doctor') else ('campus' if mode == 'password' else 'guide')
    theme=AUTH_MODULES[module]
    if form is not None and module != 'guide' and 'age' in form.fields:
        form.fields['age'].help_text='选填，用于完善个人资料。'
    if mode in ('login','register'):
        if mode == 'register' and context.get('registration_disabled'):
            title = '校园账号说明'
            subtitle = '校园账号采用学号制，由学校管理员统一导入。'
            action = '使用学号登录'
        else:
            title=theme['name'] + ('登录' if mode == 'login' else '注册')
            subtitle=('登录后进入' if mode == 'login' else '填写姓名、性别和账号信息后进入')+theme['name']+'。已有校园账号可直接使用。'
            action=('登录并进入' if mode == 'login' else '注册并进入')+theme['name']
    login_url=reverse('login') if module == 'campus' else reverse(module+'-login')
    register_url=reverse('register') if module == 'campus' else reverse(module+'-register')
    return render(request, 'accounts/auth.html', {'form': form, 'mode': mode, 'title': title,
        'subtitle': subtitle, 'action': action, 'next_url': next_destination(request,module),
        'auth_theme':theme,'auth_module':module,'module_login_url':login_url,'module_register_url':register_url, **context})


@never_cache
@login_required(login_url='guide-login')
def guide(request):
    if DoctorProfile.objects.filter(user=request.user,active=True,department__active=True).exists():
        return redirect('doctor-dashboard')
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None or not profile.is_complete:
        return redirect('profile')
    return render(request, 'guide/index.html', {'profile': profile, 'advanced_parts': PARTS,
        'inbox_unread': Consultation.objects.filter(user=request.user, status='replied', reply_read=False).count(), 'user_details': {
        'full_name': profile.full_name, 'gender': profile.get_gender_display(), 'age': profile.age,
    }})


@never_cache
@sensitive_post_parameters()
@require_http_methods(['GET', 'POST'])
def register(request, module=None):
    if request.user.is_authenticated:
        return redirect(next_destination(request,module))
    return auth_page(request, None, 'register', module=module, registration_disabled=True)


@never_cache
@sensitive_post_parameters()
@require_http_methods(['GET', 'POST'])
def sign_in(request, module=None):
    # Compatibility for saved links from the former shared administrator login.
    from urllib.parse import urlsplit, urlencode
    from campus.management_views import sign_in as management_sign_in
    path = urlsplit(request.POST.get('next') or request.GET.get('next') or '').path
    role = ('booking' if path.startswith(('/campus-admin/bookings/', '/campus-admin/venues/')) else
            'campus' if path.startswith('/campus-admin/') else 'doctor' if path.startswith('/doctor/') else None)
    if role:
        if request.method == 'POST':
            return management_sign_in(request, role)
        return redirect(reverse('management-login', args=[role]) + '?' + urlencode({'next': request.GET.get('next', '')}))
    if request.user.is_authenticated:
        return redirect(next_destination(request,module))
    form = SignInForm(request, data=request.POST if request.method == 'POST' else None)
    form.fields['username'].label = '学号'
    form.fields['username'].widget.attrs['placeholder'] = '请输入学号'
    if request.method == 'POST' and form.is_valid():
        auth_login(request, form.get_user())
        profile = Profile.objects.filter(user=form.get_user()).first()
        if profile and profile.must_change_password:
            request.session['password_change_next'] = next_destination(request,module)
            return redirect('password-change')
        return redirect(next_destination(request,module))
    return auth_page(request, form, 'login',module=module)


@never_cache
@require_POST
def sign_out(request):
    auth_logout(request)
    return redirect('login')


@never_cache
@login_required
@sensitive_post_parameters()
@require_http_methods(['GET', 'POST'])
def profile(request):
    existing = Profile.objects.filter(user=request.user).first()
    initial = {'full_name': existing.full_name, 'gender': existing.gender, 'age': existing.age,'hometown_province':existing.hometown_province,'hometown_city':existing.hometown_city} if existing else {}
    form = ProfileFields(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            Profile.objects.update_or_create(user=request.user, defaults=form.cleaned_data)
            request.user.first_name = form.cleaned_data['full_name']
            request.user.save(update_fields=['first_name'])
        return redirect('home')
    return auth_page(request, form, 'profile', profile_complete=bool(existing and existing.is_complete))


@never_cache
@login_required
@sensitive_post_parameters()
@require_http_methods(['GET', 'POST'])
def password_change(request):
    must_confirm = bool(getattr(getattr(request.user, 'guide_profile', None), 'must_change_password', False))
    form_class = FirstLoginPasswordChangeForm if must_confirm else PasswordChangeForm
    form = form_class(request.user, request.POST if request.method == 'POST' else None)
    for name, label, placeholder in (
        ('old_password', '当前密码', '初始密码为你的学号'),
        ('new_password1', '新密码', '至少 8 位，不能为纯数字'),
        ('new_password2', '确认新密码', '再次输入新密码'),
    ):
        form.fields[name].label = label
        form.fields[name].widget.attrs.update(placeholder=placeholder, autocomplete='current-password' if name == 'old_password' else 'new-password')
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        Profile.objects.filter(user=user).update(must_change_password=False)
        destination = request.session.pop('password_change_next', None) or reverse('home')
        return redirect(destination)
    return auth_page(request, form, 'password', password_change_required=must_confirm)


@never_cache
@sensitive_post_parameters()
@require_http_methods(['GET', 'POST'])
def activate(request, token):
    from .activation import user_from_token
    try:
        user = user_from_token(token)
    except (signing.BadSignature, signing.SignatureExpired, User.DoesNotExist):
        return render(request, 'accounts/activate.html', {'invalid_token': True}, status=400)
    form = StudentActivationForm(user, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        auth_login(request, user)
        return redirect('home')
    return render(request, 'accounts/activate.html', {'form': form, 'masked_number': '••••' + user.username[-4:]})
