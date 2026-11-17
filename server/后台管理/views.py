from datetime import timedelta
from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from 帖子.models import post, like, report, comment, profile, recharge, risk_alert, announcement
from 帖子.forms import recharge_review_form, announcement_form
from 帖子.risk import clear_moderated_content
from decimal import Decimal

from campus.management_views import role_required

staff_only = role_required('campus')

@staff_only
def dashboard(request):
    users = get_user_model().objects.filter(profile__isnull=False)
    today = timezone.localdate()
    start = today - timedelta(days=6)
    registrations = dict(users.filter(date_joined__date__gte=start).annotate(day=TruncDate('date_joined')).values('day').annotate(total=Count('pk')).values_list('day', 'total'))
    likes = dict(like.objects.filter(created_at__date__gte=start).annotate(day=TruncDate('created_at')).values('day').annotate(total=Count('pk')).values_list('day', 'total'))
    trend = []
    peak = max([1] + list(registrations.values()) + list(likes.values()))
    for offset in range(7):
        day = start + timedelta(days=offset)
        registered = registrations.get(day, 0)
        liked = likes.get(day, 0)
        trend.append({'day': day, 'registered': registered, 'liked': liked, 'register_width': registered * 100 / peak, 'like_width': liked * 100 / peak})
    status = request.GET.get('status', 'pending')
    if status not in ['pending', 'kept', 'hidden', 'all']:
        status = 'pending'
    reports = report.objects.select_related('user', 'post', 'reviewer').order_by('-created_at')
    if status != 'all':
        reports = reports.filter(status=status)
    from django.core.paginator import Paginator
    page = Paginator(reports, 10).get_page(request.GET.get('page'))
    context = {'user_count': users.count(), 'today_users': users.filter(date_joined__date=today).count(), 'post_count': post.objects.count(), 'hidden_count': post.objects.filter(is_hidden=True).count(), 'like_count': like.objects.count(), 'comment_count': comment.objects.count(), 'pending_count': report.objects.filter(status='pending').count(), 'report_count': report.objects.count(), 'risk_pending': risk_alert.objects.filter(status='pending').count(), 'trend': trend, 'reports': page, 'status': status}
    from 跑腿.models import task, question
    context.update({'errand_total': task.objects.count(), 'errand_completed': task.objects.filter(status='completed').count(), 'question_pending': question.objects.filter(status='pending').count()})
    context.update({'recharge_pending': recharge.objects.filter(status='pending').count(), 'recharge_total': recharge.objects.filter(status='approved').aggregate(total=Sum('amount'))['total'] or 0})
    return render(request, '后台管理/dashboard.html', context)

@staff_only
def review(request, pk):
    item = get_object_or_404(report.objects.select_related('post', 'user', 'reviewer'), pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        note = request.POST.get('note', '').strip()
        if action not in ['keep', 'hide'] or len(note) > 500:
            messages.error(request, '请选择审核操作，备注最多 500 字')
            return redirect('campus:review_report', pk=pk)
        with transaction.atomic():
            item = get_object_or_404(report.objects.select_for_update(), pk=pk)
            if item.status != 'pending':
                messages.info(request, '该举报已经审核过了')
            else:
                item.status = 'hidden' if action == 'hide' else 'kept'
                item.reviewer = request.user
                item.reviewed_at = timezone.now()
                item.review_note = note
                item.save()
                if action == 'hide' and item.post_id:
                    post.objects.filter(pk=item.post_id).update(is_hidden=True)
                messages.success(request, '审核完成')
        return redirect('campus:dashboard')
    return render(request, '后台管理/review.html', {'item': item})

@staff_only
def recharges(request):
    from django.core.paginator import Paginator
    status = request.GET.get('status', 'pending')
    if status not in ['pending', 'approved', 'rejected', 'all']:
        status = 'pending'
    records = recharge.objects.select_related('user', 'reviewer').order_by('-created_at')
    if status != 'all':
        records = records.filter(status=status)
    page = Paginator(records, 15).get_page(request.GET.get('page'))
    return render(request, '后台管理/recharges.html', {'records': page, 'status': status})

@staff_only
def review_recharge(request, pk):
    item = get_object_or_404(recharge.objects.select_related('user', 'reviewer'), pk=pk)
    form = recharge_review_form(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            item = get_object_or_404(recharge.objects.select_for_update(), pk=pk)
            if item.status != 'pending':
                messages.info(request, '该申请已审核，不会重复充值')
                return redirect('campus:review_recharge', pk=pk)
            amount = data['amount'] if data['action'] == 'approve' else Decimal('0.00')
            person, created = profile.objects.get_or_create(user=item.user)
            if data['action'] == 'approve' and not profile.objects.filter(pk=person.pk, balance__lte=Decimal('9999999999.99') - amount).exists():
                form.add_error('amount', '充值后余额超出允许范围')
            else:
                # 条件更新保证同一申请只到账一次，余额也在同一事务内更新。
                updated = recharge.objects.filter(pk=pk, status='pending').update(status='approved' if data['action'] == 'approve' else 'rejected', amount=amount, reviewer=request.user, reviewed_at=timezone.now(), note=data['note'])
                if updated and data['action'] == 'approve':
                    profile.objects.filter(pk=person.pk).update(balance=F('balance') + amount)
                messages.success(request, '审核通过，余额充值成功' if data['action'] == 'approve' else '已拒绝充值申请')
                return redirect('campus:recharges')
    return render(request, '后台管理/recharge_review.html', {'item': item, 'form': form})


@staff_only
def errand_orders(request):
    from 跑腿.models import task
    from django.db.models import Q
    from django.core.paginator import Paginator
    keyword = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    items = task.objects.select_related('owner', 'runner').order_by('-created_at')
    if keyword:
        items = items.filter(Q(title__icontains=keyword) | Q(owner__username__icontains=keyword) | Q(runner__username__icontains=keyword))
    if status in ['open', 'accepted', 'delivered', 'completed', 'cancelled']:
        items = items.filter(status=status)
    return render(request, '后台管理/errands.html', {'page': Paginator(items, 15).get_page(request.GET.get('page')), 'keyword': keyword, 'status': status})

@staff_only
def errand_order(request, pk):
    from 跑腿.models import task
    item = get_object_or_404(task.objects.select_related('owner', 'runner'), pk=pk)
    return render(request, '后台管理/errand.html', {'item': item, 'events': item.events.select_related('actor').order_by('created_at'), 'records': item.wallet_record_set.select_related('user').order_by('created_at'), 'questions': item.question_set.select_related('user').order_by('-created_at')})

@staff_only
def errand_questions(request):
    from 跑腿.models import question
    from django.core.paginator import Paginator
    items = question.objects.select_related('user', 'task').order_by('-updated_at')
    status = request.GET.get('status', 'pending')
    if status not in ['pending', 'replied', 'closed', 'all']:
        status = 'pending'
    if status != 'all':
        items = items.filter(status=status)
    return render(request, '后台管理/questions.html', {'page': Paginator(items, 15).get_page(request.GET.get('page')), 'status': status})

@staff_only
def errand_question(request, pk):
    from 跑腿.models import question, question_reply
    from 跑腿.forms import question_form
    item = get_object_or_404(question.objects.select_related('user', 'task'), pk=pk)
    form = question_form(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            question_reply.objects.create(question=item, author=request.user, content=form.cleaned_data['content'])
            item.status = 'replied'
            item.reply_unread = True
            item.save()
        messages.success(request, '已联系用户，回复会在用户消息中提醒')
        return redirect('campus:admin_question', pk=pk)
    return render(request, '后台管理/question.html', {'item': item, 'form': form, 'replies': item.replies.select_related('author').order_by('created_at')})

@staff_only
def risk_alerts(request):
    from django.core.paginator import Paginator
    status = request.GET.get('status', 'pending')
    if status not in ['pending', 'cleared', 'hidden', 'all']:
        status = 'pending'
    items = risk_alert.objects.select_related('reviewer').order_by('-created_at')
    if status != 'all':
        items = items.filter(status=status)
    return render(request, '后台管理/risks.html', {'page': Paginator(items, 15).get_page(request.GET.get('page')), 'status': status})

@staff_only
def review_risk(request, pk):
    item = get_object_or_404(risk_alert.objects.select_related('reviewer'), pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action not in ['keep', 'hide']:
            messages.error(request, '请选择审核结果')
            return redirect('campus:review_risk', pk=pk)
        with transaction.atomic():
            item = get_object_or_404(risk_alert.objects.select_for_update(), pk=pk)
            if item.status != 'pending':
                messages.info(request, '这条内容已审核')
            else:
                if action == 'hide':
                    clear_moderated_content(item)
                    item.status = 'hidden'
                else:
                    item.status = 'cleared'
                item.reviewer = request.user
                item.reviewed_at = timezone.now()
                item.save(update_fields=['status', 'reviewer', 'reviewed_at'])
                messages.success(request, '已隐藏内容' if action == 'hide' else '已确认内容正常')
        return redirect('campus:risk_alerts')
    source_label = {'post': '帖子', 'comment': '评论', 'chat': '私信', 'errand': '跑腿订单', 'question': '用户咨询'}.get(item.source_type, '内容')
    return render(request, '后台管理/risk_review.html', {'item': item, 'source_label': source_label, 'can_hide': item.source_type in ['post', 'comment', 'chat']})

@staff_only
def ai_console(request):
    from datetime import timedelta
    from django.db.models import Count, Avg
    since = timezone.now() - timedelta(days=30)
    alerts = risk_alert.objects.filter(created_at__gte=since)
    total = alerts.count()
    reviewed = alerts.exclude(status='pending').count()
    hidden = alerts.filter(status='hidden').count()
    avg_score = alerts.aggregate(value=Avg('score'))['value'] or 0
    by_source = list(alerts.values('source_type').annotate(total=Count('pk')).order_by('-total'))
    source_names = {'post': '帖子', 'comment': '评论', 'chat': '私信', 'errand': '跑腿订单', 'question': '用户咨询'}
    for row in by_source:
        row['label'] = source_names.get(row['source_type'], '其他内容')
        row['width'] = round(row['total'] * 100 / max(1, total))
    pending = alerts.filter(status='pending').count()
    review_rate = round(reviewed * 100 / max(1, total)) if total else 0
    context = {
        'total': total, 'pending': pending, 'reviewed': reviewed,
        'hidden': hidden, 'avg_score': round(avg_score, 1),
        'review_rate': review_rate, 'by_source': by_source,
        'recent': alerts.order_by('-created_at')[:8],
    }
    return render(request, '后台管理/ai_console.html', context)

@staff_only
def announcements(request):
    form = announcement_form(request.POST or None)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create' and form.is_valid():
            item = form.save(commit=False)
            item.author = request.user
            item.save()
            messages.success(request, '公告已置顶到校园广场')
            return redirect('campus:admin_announcements')
        if action in ['toggle', 'delete']:
            item = get_object_or_404(announcement, pk=request.POST.get('pk'))
            if action == 'toggle':
                item.is_active = not item.is_active
                item.save(update_fields=['is_active'])
                messages.success(request, '公告显示状态已更新')
            else:
                item.delete()
                messages.success(request, '公告已删除')
            return redirect('campus:admin_announcements')
    return render(request, '后台管理/announcements.html', {'form': form, 'items': announcement.objects.select_related('author')[:30]})

from campus.audit import audit_change
review=audit_change('campus','帖子.report',('status',),'审核举报')(review)
review_risk=audit_change('campus','帖子.risk_alert',('status',),'复核风险')(review_risk)
review_recharge=audit_change('campus','帖子.recharge',('status',),'审核充值')(review_recharge)
errand_question=audit_change('campus','跑腿.question',('status','updated_at'),'回复跑腿咨询')(errand_question)
