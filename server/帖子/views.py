from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .forms import post_form, comment_form
from .models import post, history, favorite, like, report
from django.http import Http404
from django.urls import reverse
from django.db.models import F
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST
from 个人信息.social import friends_for
from .models import tag, user_activity
from .risk import flag_content
import hashlib
import unicodedata
from difflib import SequenceMatcher
from datetime import timedelta

def store_tags(item, values):
    selected = []
    for value in values:
        name = unicodedata.normalize('NFC', value.strip().lstrip('#'))
        slug = name.casefold()
        label, created = tag.objects.get_or_create(slug=slug, defaults={'name': name})
        selected.append(label)
    item.tags.set(selected)

def post_fingerprint(title, content):
    normalize = lambda value: ''.join(char.casefold() for char in unicodedata.normalize('NFKC', value) if char.isalnum())
    return hashlib.sha256((normalize(title) + normalize(content)).encode('utf-8')).hexdigest()

def duplicate_post_error(user, title, content):
    normalize = lambda value: ''.join(char.casefold() for char in unicodedata.normalize('NFKC', value) if char.isalnum())
    combined = normalize(title) + normalize(content)
    fingerprint = post_fingerprint(title, content)
    recent = post.objects.filter(author=user, created_at__gte=timezone.now() - timezone.timedelta(hours=24)).order_by('-created_at')[:100]
    for previous in recent:
        if previous.duplicate_key == fingerprint:
            return '这条帖子和你最近发布的内容重复了，请直接修改原帖。'
        old = normalize(previous.title) + normalize(previous.content)
        if len(combined) >= 24 and len(old) >= 24 and SequenceMatcher(None, combined, old, autojunk=False).ratio() >= 0.92:
            return '这条帖子和你最近发布的内容很相似，请补充新信息或修改原帖。'
    if post.objects.filter(author=user, created_at__gte=timezone.now() - timezone.timedelta(minutes=2)).count() >= 4:
        return '你发帖有点快，请等一会儿再发，避免重复内容影响广场统计。'
    return ''

def detail(request, pk):
    item = get_object_or_404(post.objects.select_related('author'), pk=pk)
    if item.is_hidden and not request.user.is_campus_manager:
        raise Http404('该帖子已下架')
    if request.method == 'GET':
        seen = request.session.get('seen_posts', {})
        if str(pk) not in seen:
            post.objects.filter(pk=pk).update(view_count=F('view_count') + 1)
            item.view_count += 1
        seen[str(pk)] = timezone.now().isoformat()
        request.session['seen_posts'] = dict(list(seen.items())[-500:])
    if request.user.is_authenticated and request.method == 'GET':
        history.objects.update_or_create(user=request.user, post=item)
        activity_seen = request.session.get('activity_posts', {})
        viewed_at = activity_seen.get(str(pk))
        try:
            last_activity = timezone.datetime.fromisoformat(viewed_at) if viewed_at else None
            if last_activity and timezone.is_naive(last_activity):
                last_activity = timezone.make_aware(last_activity, timezone.get_current_timezone())
        except (TypeError, ValueError):
            last_activity = None
        now = timezone.now()
        if not last_activity or now - last_activity >= timedelta(minutes=30):
            user_activity.objects.create(user=request.user, action='post_view', category=item.category)
        activity_seen[str(pk)] = now.isoformat()
        request.session['activity_posts'] = dict(list(activity_seen.items())[-300:])
    form = comment_form(request.POST or None)
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('campus:login')
        if form.is_valid():
            reply = form.save(commit=False)
            reply.post = item
            reply.author = request.user
            reply.save()
            flag_content('comment', reply.pk, request.user, reply.content)
            messages.success(request, '评论发布成功')
            return redirect('campus:post_detail', pk=pk)
    replies = item.comments.filter(is_hidden=False).select_related('author').order_by('created_at')
    return render(request, '帖子/detail.html', {'item': item, 'replies': replies, 'form': form, 'like_count': item.likes.count(), 'is_liked': request.user.is_authenticated and like.objects.filter(user=request.user, post=item).exists(), 'is_favorite': request.user.is_authenticated and favorite.objects.filter(user=request.user, post=item).exists(), 'share_friends': friends_for(request.user) if request.user.is_authenticated else []})

@login_required
@transaction.atomic
def create(request):
    from campus import service_plans
    plan=service_plans.post_plan(request)
    initial={'quoted_post': request.GET.get('quote')}
    if plan:initial['category']='交友'
    form = post_form(request.POST or None, request.FILES or None, initial=initial if request.method == 'GET' else None)
    if request.method == 'POST' and form.is_valid():
        error = duplicate_post_error(request.user, form.cleaned_data['title'], form.cleaned_data['content'])
        if error:
            form.add_error(None, error)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.author = request.user
        item.duplicate_key = post_fingerprint(item.title, item.content)
        item.save()
        store_tags(item, form.cleaned_data['tags_text'])
        flag_content('post', item.pk, request.user, item.title + '\n' + item.content)
        messages.success(request, '发帖成功')
        if service_plans.post_completed(request,plan,item):return redirect(reverse('task-assistant')+'#service-plan-panel')
        return redirect('campus:post_detail', pk=item.pk)
    return render(request, '帖子/form.html', {'form': form, 'title': '发布帖子','service_plan':plan})

@login_required
def edit(request, pk):
    item = get_object_or_404(post, pk=pk, author=request.user)
    form = post_form(request.POST or None, request.FILES or None, instance=item)
    if request.method == 'POST' and form.is_valid():
        error = duplicate_post_error(request.user, form.cleaned_data['title'], form.cleaned_data['content'])
        if error and (form.cleaned_data['title'] != item.title or form.cleaned_data['content'] != item.content):
            form.add_error(None, error)
    if request.method == 'POST' and form.is_valid():
        item = form.save()
        item.duplicate_key = post_fingerprint(item.title, item.content)
        item.save(update_fields=['duplicate_key'])
        store_tags(item, form.cleaned_data['tags_text'])
        flag_content('post', item.pk, request.user, item.title + '\n' + item.content)
        messages.success(request, '帖子已修改')
        return redirect('campus:post_detail', pk=pk)
    return render(request, '帖子/form.html', {'form': form, 'title': '修改帖子'})

@login_required
def delete(request, pk):
    item = get_object_or_404(post, pk=pk, author=request.user)
    if request.method == 'POST':
        item.delete()
        messages.success(request, '帖子已删除')
        return redirect('campus:profile')
    return render(request, '帖子/delete.html', {'item': item})

@login_required
@require_POST
def toggle_favorite(request, pk):
    item = get_object_or_404(post, pk=pk)
    row, created = favorite.objects.get_or_create(user=request.user, post=item)
    if not created:
        row.delete()
    else:
        user_activity.objects.create(user=request.user, action='post_favorite', category=item.category)
    return redirect('campus:post_detail', pk=pk)

@login_required
@require_POST
def toggle_like(request, pk):
    item = get_object_or_404(post, pk=pk, is_hidden=False)
    row, created = like.objects.get_or_create(user=request.user, post=item)
    if not created:
        row.delete()
    else:
        user_activity.objects.create(user=request.user, action='post_like', category=item.category)
    return redirect('campus:post_detail', pk=pk)

@login_required
def report_post(request, pk):
    item = get_object_or_404(post, pk=pk, is_hidden=False)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason or len(reason) > 500:
            messages.error(request, '请填写 1 到 500 字的举报原因')
        elif report.objects.filter(user=request.user, post=item, status='pending').exists():
            messages.info(request, '你已经举报过这个帖子，正在等待审核')
            return redirect('campus:post_detail', pk=pk)
        else:
            report.objects.create(user=request.user, post=item, title=item.title, content=item.content, reason=reason)
            messages.success(request, '举报已提交，等待管理员审核')
            return redirect('campus:post_detail', pk=pk)
    return render(request, '帖子/report.html', {'item': item})
