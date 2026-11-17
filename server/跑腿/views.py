from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from 帖子.models import profile, user_activity
from 帖子.risk import flag_content
from .forms import task_form, delivery_form, question_form
from .models import task, task_event, wallet_record, question, question_reply, task_types

def index(request):
    if request.user.is_authenticated:
        last_visit = request.session.get('errand_last_visit', '')
        previous = timezone.datetime.fromisoformat(last_visit) if last_visit else None
        if not previous or timezone.now() - previous > timezone.timedelta(minutes=30):
            user_activity.objects.create(user=request.user, action='errand_open')
            request.session['errand_last_visit'] = timezone.now().isoformat()
    items = task.objects.filter(status__in=['open', 'accepted', 'delivered']).select_related('owner', 'runner')
    keyword = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    category = request.GET.get('category', '')
    if keyword:
        items = items.filter(Q(title__icontains=keyword) | Q(description__icontains=keyword))
    if status in ['open', 'accepted', 'delivered']:
        items = items.filter(status=status)
    if category:
        items = items.filter(category=category)
    sort = request.GET.get('sort', 'new')
    items = items.order_by('-price', '-created_at') if sort == 'price' else items.order_by('-created_at')
    person = profile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    return render(request, '跑腿/index.html', {'page': Paginator(items, 9).get_page(request.GET.get('page')), 'keyword': keyword, 'status': status, 'category': category, 'sort': sort, 'types': task_types, 'person': person, 'open_count': task.objects.filter(status='open').count(), 'active_count': task.objects.filter(status__in=['accepted', 'delivered']).count()})

@login_required
def create(request):
    person, created = profile.objects.get_or_create(user=request.user)
    form = task_form(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            amount = form.cleaned_data['price']
            # 余额不足时不创建订单，预付与订单创建一起提交。
            paid = profile.objects.filter(pk=person.pk, balance__gte=amount).update(balance=F('balance') - amount)
            if not paid:
                form.add_error('price', '余额不足，请先充值')
            else:
                item = form.save(commit=False)
                item.owner = request.user
                item.save()
                wallet_record.objects.create(user=request.user, task=item, kind='payment', amount=amount)
                task_event.objects.create(task=item, actor=request.user, text='发布订单并预付悬赏')
                user_activity.objects.create(user=request.user, action='errand_create')
                flag_content('errand', item.pk, request.user, item.title + '\n' + item.description)
                messages.success(request, '支付成功，订单已发布，等待接单')
                return redirect('campus:errand_detail', pk=item.pk)
        person.refresh_from_db()
    return render(request, '跑腿/create.html', {'form': form, 'person': person})

def detail(request, pk):
    item = get_object_or_404(task.objects.select_related('owner', 'runner'), pk=pk)
    participant = request.user.is_authenticated and request.user.pk in [item.owner_id, item.runner_id]
    if item.status in ['completed', 'cancelled'] and not participant and not request.user.is_campus_manager:
        raise Http404()
    # 地址和手机号不放在公开列表或隐藏元素中。
    return render(request, '跑腿/detail.html', {'item': item, 'private_visible': participant, 'can_proof': participant or request.user.is_campus_manager, 'events': item.events.select_related('actor').order_by('created_at'), 'delivery_form': delivery_form() if request.user.pk == item.runner_id and item.status == 'accepted' else None})

@login_required
@require_POST
def take(request, pk):
    with transaction.atomic():
        item = get_object_or_404(task, pk=pk)
        if item.owner_id == request.user.pk:
            messages.error(request, '不能接自己的订单')
        elif task.objects.filter(pk=pk, status='open', runner__isnull=True).update(runner=request.user, status='accepted', accepted_at=timezone.now()):
            task_event.objects.create(task=item, actor=request.user, text='接单成功')
            user_activity.objects.create(user=request.user, action='errand_take')
            messages.success(request, '接单成功，现在可以查看地址和手机号')
        else:
            messages.info(request, '订单已被接单或已关闭')
    return redirect('campus:errand_detail', pk=pk)

@login_required
@require_POST
def cancel(request, pk):
    with transaction.atomic():
        item = get_object_or_404(task, pk=pk, owner=request.user)
        person, created = profile.objects.get_or_create(user=request.user)
        if item.status != 'open':
            messages.error(request, '只有未接单的订单可以取消；其他问题请联系管理员')
        elif not profile.objects.filter(pk=person.pk, balance__lte=Decimal('9999999999.99') - item.price).exists():
            messages.error(request, '余额超出范围，请联系管理员')
        elif task.objects.filter(pk=pk, status='open').update(status='cancelled'):
            profile.objects.filter(pk=person.pk).update(balance=F('balance') + item.price)
            wallet_record.objects.create(user=request.user, task=item, kind='refund', amount=item.price)
            task_event.objects.create(task=item, actor=request.user, text='取消未接单订单，已原路退回余额')
            messages.success(request, '订单已取消，预付款已退回余额')
    return redirect('campus:errand_detail', pk=pk)

@login_required
@require_POST
def deliver(request, pk):
    item = get_object_or_404(task, pk=pk, runner=request.user)
    form = delivery_form(request.POST, request.FILES)
    if item.status != 'accepted':
        messages.error(request, '当前订单不能重复提交送达照片')
        return redirect('campus:errand_detail', pk=pk)
    if form.is_valid():
        storage = task._meta.get_field('proof').storage
        filename = storage.save('errands/' + form.cleaned_data['proof'].name, form.cleaned_data['proof'])
        try:
            with transaction.atomic():
                updated = task.objects.filter(pk=pk, runner=request.user, status='accepted').update(proof=filename, delivery_note=form.cleaned_data['delivery_note'], status='delivered', delivered_at=timezone.now())
                if updated:
                    task_event.objects.create(task=item, actor=request.user, text='上传送达照片，等待发布者确认')
                    messages.success(request, '照片已提交，等待发布者确认完成')
                else:
                    storage.delete(filename)
        except Exception:
            storage.delete(filename)
            raise
        return redirect('campus:errand_detail', pk=pk)
    return render(request, '跑腿/detail.html', {'item': item, 'private_visible': True, 'can_proof': True, 'delivery_form': form, 'events': item.events.select_related('actor').order_by('created_at')})

@login_required
@require_POST
def complete(request, pk):
    with transaction.atomic():
        item = get_object_or_404(task, pk=pk, owner=request.user)
        if item.status != 'delivered' or not item.proof or not item.runner_id:
            messages.error(request, '接单者提交送达照片后才能确认完成')
        else:
            person, created = profile.objects.get_or_create(user=item.runner)
            if not profile.objects.filter(pk=person.pk, balance__lte=Decimal('9999999999.99') - item.price).exists():
                messages.error(request, '接单者余额超出范围，请联系管理员')
            elif task.objects.filter(pk=pk, status='delivered').update(status='completed', completed_at=timezone.now()):
                profile.objects.filter(pk=person.pk).update(balance=F('balance') + item.price)
                wallet_record.objects.create(user=item.runner, task=item, kind='income', amount=item.price)
                task_event.objects.create(task=item, actor=request.user, text='发布者确认完成，悬赏已结算给接单者')
                user_activity.objects.create(user=request.user, action='errand_complete')
                messages.success(request, '订单已完成，悬赏已结算')
    return redirect('campus:errand_detail', pk=pk)

@login_required
def proof(request, pk):
    item = get_object_or_404(task, pk=pk)
    if request.user.pk not in [item.owner_id, item.runner_id] and not request.user.is_campus_manager:
        return HttpResponseForbidden('无权查看送达照片')
    if not item.proof:
        raise Http404()
    try:
        response = FileResponse(item.proof.open('rb'))
    except FileNotFoundError:
        raise Http404()
    response['Cache-Control'] = 'private, no-store'
    return response

@login_required
def mine(request):
    role = request.GET.get('role', 'owner')
    items = task.objects.filter(runner=request.user) if role == 'runner' else task.objects.filter(owner=request.user)
    records = wallet_record.objects.filter(user=request.user).select_related('task').order_by('-created_at')[:20]
    return render(request, '跑腿/mine.html', {'page': Paginator(items.select_related('owner', 'runner').order_by('-created_at'), 12).get_page(request.GET.get('page')), 'role': role, 'records': records})

@login_required
def questions(request):
    form = question_form(request.POST or None)
    related = None
    task_id = request.POST.get('task', '') if request.method == 'POST' else request.GET.get('task', '')
    if task_id:
        if not task_id.isdecimal():
            raise Http404()
        related = get_object_or_404(task.objects.filter(Q(owner=request.user) | Q(runner=request.user)), pk=task_id)
    if request.method == 'POST' and form.is_valid():
        item = question.objects.create(user=request.user, task=related, content=form.cleaned_data['content'])
        flag_content('question', item.pk, request.user, item.content)
        messages.success(request, '问题已提交，等待管理员联系')
        return redirect('campus:errand_question', pk=item.pk)
    items = question.objects.filter(user=request.user).select_related('task').order_by('-updated_at')
    orders = task.objects.filter(Q(owner=request.user) | Q(runner=request.user)).order_by('-created_at')
    return render(request, '跑腿/questions.html', {'form': form, 'items': items, 'related': related, 'orders': orders})

@login_required
def question_detail(request, pk):
    item = get_object_or_404(question, pk=pk, user=request.user)
    form = question_form(request.POST or None)
    if request.method == 'POST':
        if request.POST.get('action') == 'close':
            item.status = 'closed'
            item.reply_unread = False
            item.save()
            messages.success(request, '已标记为解决')
            return redirect('campus:errand_question', pk=pk)
        if form.is_valid():
            question_reply.objects.create(question=item, author=request.user, content=form.cleaned_data['content'])
            flag_content('question', item.pk, request.user, item.content + '\n' + form.cleaned_data['content'])
            item.status = 'pending'
            item.reply_unread = False
            item.save()
            return redirect('campus:errand_question', pk=pk)
    question.objects.filter(pk=pk, user=request.user).update(reply_unread=False)
    return render(request, '跑腿/question.html', {'item': item, 'form': form, 'replies': item.replies.select_related('author').order_by('created_at')})
