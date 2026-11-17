"""Clearly labelled simulated top-ups for the existing demonstration wallet."""
from datetime import timedelta
from decimal import Decimal
import uuid
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from .models import DemoTopUp
from .ui_language import translate
from 帖子.models import profile, recharge

SALT='campus-demo-topup-v1'
MAX_BALANCE=Decimal('9999999999.99')

class TopUpForm(forms.Form):
    amount=forms.DecimalField(label='充值金额',min_value=Decimal('1'),max_value=Decimal('500'),max_digits=5,decimal_places=2,initial=20,widget=forms.NumberInput(attrs={'step':'.01','min':'1','max':'500','inputmode':'decimal'}))
    method=forms.ChoiceField(label='模拟支付方式',choices=[('alipay','支付宝（模拟）'),('wechat','微信支付（模拟）')],widget=forms.RadioSelect)
    request_token=forms.CharField(widget=forms.HiddenInput)

def enabled():return getattr(settings,'DEMO_PAYMENTS_ENABLED',True)

def expire(order):
    if order.status=='pending' and order.expires_at<=timezone.now():
        DemoTopUp.objects.filter(pk=order.pk,status='pending').update(status='expired')
        order.refresh_from_db()

@login_required
@require_http_methods(['GET','POST'])
def index(request):
    if not enabled():return HttpResponseForbidden(translate('模拟充值已停用。',request.session.get('campus_language','zh')))
    person,_=profile.objects.get_or_create(user=request.user)
    token=signing.dumps({'user':request.user.pk,'key':str(uuid.uuid4())},salt=SALT)
    form=TopUpForm(request.POST if request.method=='POST' else None,initial={'request_token':token,'method':'alipay'})
    if request.method=='POST' and form.is_valid():
        try:
            signed=signing.loads(form.cleaned_data['request_token'],salt=SALT,max_age=3600)
            if signed.get('user')!=request.user.pk:raise ValueError()
            key=uuid.UUID(signed['key'])
        except (signing.BadSignature,ValueError,KeyError,TypeError):
            form.add_error(None,'页面已失效，请刷新后重新充值。')
        else:
            order,created=DemoTopUp.objects.get_or_create(user=request.user,request_key=key,defaults={'amount':form.cleaned_data['amount'],'method':form.cleaned_data['method'],'expires_at':timezone.now()+timedelta(minutes=15)})
            if not created and (order.amount!=form.cleaned_data['amount'] or order.method!=form.cleaned_data['method']):
                return HttpResponseBadRequest('充值信息已改变，请刷新页面重新提交。')
            return redirect('campus:demo-checkout',pk=order.pk)
    DemoTopUp.objects.filter(user=request.user,status='pending',expires_at__lte=timezone.now()).update(status='expired')
    orders=Paginator(DemoTopUp.objects.filter(user=request.user),12).get_page(request.GET.get('page'))
    return render(request,'campus/payments/topup.html',{'person':person,'form':form,'orders':orders,'legacy':recharge.objects.filter(user=request.user).exclude(code__startswith='DEMO-').order_by('-created_at')[:12]})

@login_required
@require_http_methods(['GET'])
def checkout(request,pk):
    order=get_object_or_404(DemoTopUp,pk=pk,user=request.user)
    expire(order)
    person,_=profile.objects.get_or_create(user=request.user)
    return render(request,'campus/payments/checkout.html',{'order':order,'person':person,'payments_enabled':enabled()})

@login_required
@require_POST
def complete(request,pk):
    if not enabled():return HttpResponseForbidden('模拟充值已停用。')
    order=get_object_or_404(DemoTopUp,pk=pk,user=request.user)
    action=request.POST.get('action')
    if action not in ('pay','cancel','fail'):return HttpResponseBadRequest('无效操作')
    expire(order)
    if order.status!='pending':return redirect('campus:demo-checkout',pk=pk)
    now=timezone.now()
    if action!='pay':
        DemoTopUp.objects.filter(pk=pk,user=request.user,status='pending').update(status='cancelled' if action=='cancel' else 'failed')
        return redirect('campus:demo-checkout',pk=pk)
    try:
        with transaction.atomic():
            # Claim the state before crediting: retries and duplicate tabs cannot double-credit.
            claimed=DemoTopUp.objects.filter(pk=pk,user=request.user,status='pending',expires_at__gt=now).update(status='paid',paid_at=now)
            if claimed:
                person,_=profile.objects.get_or_create(user=request.user)
                credited=profile.objects.filter(pk=person.pk,balance__lte=MAX_BALANCE-order.amount).update(balance=F('balance')+order.amount)
                if not credited:raise ValidationError('余额已达上限，请联系管理员。')
                recharge.objects.create(user=request.user,code=order.reference,amount=order.amount,status='approved',reviewed_at=now,note='模拟支付自动入账，不涉及真实资金。')
    except ValidationError:
        messages.error(request,'余额已达上限，请联系管理员。')
    return redirect('campus:demo-checkout',pk=pk)
