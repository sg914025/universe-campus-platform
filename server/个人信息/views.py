from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from .social import are_friends, friends_for
from 帖子.models import profile, post, history, favorite, follow, chat_message, recharge, user_activity, comment, like
from 帖子.forms import profile_form, recharge_form
from 帖子.risk import flag_content

@login_required
def info(request):
    person, created = profile.objects.get_or_create(user=request.user)
    posts = post.objects.filter(author=request.user).order_by('-created_at')
    histories = history.objects.filter(user=request.user, post__is_hidden=False).select_related('post').order_by('-viewed_at')
    favorites = favorite.objects.filter(user=request.user, post__is_hidden=False).select_related('post').order_by('-created_at')
    following = list(follow.objects.filter(user=request.user).select_related('target', 'target__profile').order_by('-created_at'))
    friend_ids = set(friends_for(request.user).values_list('pk', flat=True))
    for row in following:
        row.is_friend = row.target_id in friend_ids
    from 跑腿.models import task
    experience = post.objects.filter(author=request.user, is_hidden=False).count() * 10 + comment.objects.filter(author=request.user, is_hidden=False).count() * 5 + like.objects.filter(user=request.user, post__is_hidden=False).count() * 2 + favorite.objects.filter(user=request.user, post__is_hidden=False).count() * 2 + task.objects.filter(runner=request.user, status='completed').count() * 15
    level = experience // 100 + 1
    level_progress = experience % 100
    tab = request.GET.get('tab', 'posts')
    if tab not in ['posts', 'history', 'favorites', 'following']:
        tab = 'posts'
    return render(request, '个人信息/info.html', {'person': person, 'posts': posts, 'histories': histories, 'favorites': favorites, 'following': following, 'tab': tab, 'experience': experience, 'level': level, 'level_progress': level_progress, 'xp_to_next': 100 - level_progress})

@login_required
def edit(request):
    person, created = profile.objects.get_or_create(user=request.user)
    form = profile_form(request.POST or None, request.FILES or None, instance=person)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '资料已保存')
        return redirect('campus:profile')
    return render(request, '个人信息/edit.html', {'form': form, 'person': person})

@xframe_options_sameorigin
def member(request, pk):
    target = get_object_or_404(get_user_model().objects.filter(profile__isnull=False), pk=pk)
    person = profile.objects.filter(user=target).first()
    following = False
    friend = False
    if request.user.is_authenticated:
        following = follow.objects.filter(user=request.user, target=target).exists()
        friend = are_friends(request.user, target)
    return render(request, '个人信息/member.html', {'target': target, 'person': person, 'following': following, 'friend': friend, 'posts': post.objects.filter(author=target, is_hidden=False).order_by('-created_at')})

@login_required
@require_POST
def toggle_follow(request, pk):
    target = get_object_or_404(get_user_model().objects.filter(profile__isnull=False), pk=pk)
    if target != request.user:
        row, created = follow.objects.get_or_create(user=request.user, target=target)
        if not created:
            row.delete()
    return redirect('campus:member', pk=pk)

@login_required
@xframe_options_sameorigin
def chat(request, pk):
    target = get_object_or_404(get_user_model().objects.filter(profile__isnull=False), pk=pk)
    if not are_friends(request.user, target):
        return HttpResponseForbidden('双方互相关注后才能聊天和分享帖子。')
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        shared_id = request.POST.get('shared_post', '')
        shared = None
        if shared_id:
            if not shared_id.isdecimal():
                messages.error(request, '请选择有效的帖子')
                return redirect('campus:chat', pk=pk)
            shared = get_object_or_404(post, pk=int(shared_id), is_hidden=False)
        if len(content) > 2000:
            messages.error(request, '消息最多 2000 字')
        elif content or shared:
            sent = chat_message.objects.create(sender=request.user, receiver=target, content=content, shared_post=shared, shared_title=shared.title if shared else '')
            flag_content('chat', sent.pk, request.user, content)
            return redirect('campus:chat', pk=pk)
        else:
            messages.error(request, '请填写消息或选择帖子')
    chat_message.objects.filter(sender=target, receiver=request.user, is_read=False).update(is_read=True)
    chats = chat_message.objects.filter(Q(sender=request.user, receiver=target) | Q(sender=target, receiver=request.user)).select_related('shared_post', 'sender').order_by('created_at', 'pk')
    from campus.friend_services import chat_context
    chats=chats.select_related('campus_booking_share__booking__venue')
    return render(request, '个人信息/chat.html', {**chat_context(request,target),'target': target, 'chats': chats, 'selected_post': post.objects.filter(pk=int(request.GET['post']), is_hidden=False).first() if request.GET.get('post', '').isdecimal() else None})


@login_required
@xframe_options_sameorigin
def user_search(request):
    keyword = request.GET.get('q', '').strip()[:150]
    results = []
    if keyword:
        from django.core.paginator import Paginator
        matches = get_user_model().objects.filter(profile__isnull=False).filter(Q(username__icontains=keyword) | Q(profile__nickname__icontains=keyword)).exclude(pk=request.user.pk).select_related('profile').order_by('username')
        results = Paginator(matches, 12).get_page(request.GET.get('page'))
        following_ids = set(follow.objects.filter(user=request.user).values_list('target_id', flat=True))
        friend_ids = set(friends_for(request.user).values_list('pk', flat=True))
        for person in results:
            person.is_following = person.pk in following_ids
            person.is_friend = person.pk in friend_ids
    return render(request, '个人信息/search.html', {'keyword': keyword, 'results': results})

@login_required
def recharge_balance(request):
    person, created = profile.objects.get_or_create(user=request.user)
    form = recharge_form(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        from django.db import IntegrityError, transaction
        try:
            with transaction.atomic():
                recharge.objects.create(user=request.user, code=form.cleaned_data['code'])
        except IntegrityError:
            form.add_error('code', '该充值代码已经提交，请勿重复使用')
        else:
            messages.success(request, '等待后台管理员审核，通过后余额会自动到账')
            return redirect('campus:recharge')
    records = recharge.objects.filter(user=request.user).order_by('-created_at')
    return render(request, '个人信息/recharge.html', {'person': person, 'form': form, 'records': records})

@login_required
def inbox(request):
    conversations = []
    for friend in friends_for(request.user):
        chats = chat_message.objects.filter(Q(sender=request.user, receiver=friend) | Q(sender=friend, receiver=request.user))
        last = chats.select_related('shared_post').order_by('-created_at', '-pk').first()
        if last:
            unread = chats.filter(sender=friend, receiver=request.user, is_read=False).count()
            conversations.append({'friend': friend, 'last': last, 'unread': unread})
    conversations.sort(key=lambda row: row['last'].created_at, reverse=True)
    from 跑腿.models import question
    replies = question.objects.filter(user=request.user, replies__author__groups__name="campus_moderators").distinct().order_by('-updated_at')
    return render(request, '个人信息/messages.html', {'conversations': conversations, 'question_messages': replies})

@login_required
def unread_messages(request):
    from django.http import JsonResponse
    from .social import unread_for
    from 跑腿.models import question
    return JsonResponse({'count': unread_for(request.user).count() + question.objects.filter(user=request.user, reply_unread=True).count()})

@login_required
def ai_insights(request):
    from datetime import datetime, time, timedelta
    from django.db.models import Count
    from django.utils import timezone
    from 帖子.models import categories
    from 跑腿.models import task
    now = timezone.now()
    start = now - timedelta(days=30)
    visits = user_activity.objects.filter(user=request.user, action='post_view', created_at__gte=start)
    by_category = list(visits.values('category').annotate(total=Count('pk')).order_by('-total', 'category'))
    display = dict(categories)
    peak = max((row['total'] for row in by_category), default=1)
    for row in by_category:
        row['label'] = display.get(row['category'], row['category'] or '其他')
        row['width'] = round(row['total'] * 100 / peak)
    action_counts = dict(user_activity.objects.filter(user=request.user, created_at__gte=start).values('action').annotate(total=Count('pk')).values_list('action', 'total'))
    reads = visits.count()
    errands_open = action_counts.get('errand_open', 0)
    errands_taken = action_counts.get('errand_take', 0)
    errands_posted = action_counts.get('errand_create', 0)
    errands_done = action_counts.get('errand_complete', 0)
    popular = by_category[0] if by_category else None
    answer = '近 30 天你还没有浏览或跑腿记录，开始使用后这里会生成个人趋势。'
    query = request.POST.get('question', '').strip()[:200] if request.method == 'POST' else ''
    conversation = request.session.get('ai_conversation', [])
    if request.method == 'POST' and request.POST.get('action') == 'clear':
        conversation = []
        request.session['ai_conversation'] = conversation
        return redirect('campus:ai_insights')
    if query:
        if any(word in query for word in ['跑腿', '接单', '订单']):
            answer = f'近 30 天你打开跑腿广场 {errands_open} 次，发布 {errands_posted} 单，接单 {errands_taken} 次，完成 {errands_done} 单。'
            chart_title = '跑腿活动 · 近 30 天'
            chart_rows = [
                {'label': '打开', 'total': errands_open},
                {'label': '发布', 'total': errands_posted},
                {'label': '接单', 'total': errands_taken},
                {'label': '完成', 'total': errands_done},
            ]
        elif any(word in query for word in ['点赞', '收藏']):
            answer = f'近 30 天你点赞 {action_counts.get("post_like", 0)} 次，收藏 {action_counts.get("post_favorite", 0)} 次。'
            chart_title = '互动记录 · 近 30 天'
            chart_rows = [
                {'label': '点赞', 'total': action_counts.get('post_like', 0)},
                {'label': '收藏', 'total': action_counts.get('post_favorite', 0)},
            ]
        elif any(word in query for word in ['看', '浏览', '阅读', '类型', '帖子']):
            answer = f'近 30 天你打开帖子 {reads} 次。' + (f'最常浏览“{popular["label"]}”，共 {popular["total"]} 次。' if popular else '目前还没有帖子浏览记录。')
            chart_title = '阅读类型 · 近 30 天'
            chart_rows = [{'label': row['label'], 'total': row['total']} for row in by_category]
        else:
            answer = '我能根据你的记录回答帖子浏览类型、阅读次数、点赞收藏和跑腿打开、发布、接单情况。试试问“我最近看什么类型最多”或“我跑腿接了多少单”。'
            chart_title = '近期记录概览'
            chart_rows = [
                {'label': '阅读', 'total': reads},
                {'label': '跑腿', 'total': errands_open},
                {'label': '点赞', 'total': action_counts.get('post_like', 0)},
                {'label': '收藏', 'total': action_counts.get('post_favorite', 0)},
            ]
        chart_peak = max([1] + [row['total'] for row in chart_rows])
        for row in chart_rows:
            row['width'] = round(row['total'] * 100 / chart_peak)
        conversation.append({
            'question': query,
            'answer': answer,
            'chart_title': chart_title,
            'chart': chart_rows,
            'has_chart_data': any(row['total'] for row in chart_rows),
        })
        conversation = conversation[-12:]
        request.session['ai_conversation'] = conversation
    days = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).date()
        day_start = timezone.make_aware(datetime.combine(day, time.min))
        next_day = day_start + timedelta(days=1)
        day_views = visits.filter(created_at__gte=day_start, created_at__lt=next_day).count()
        day_errands = user_activity.objects.filter(user=request.user, action__startswith='errand_', created_at__gte=day_start, created_at__lt=next_day).count()
        days.append({'day': day, 'views': day_views, 'errands': day_errands})
    scale = max([1] + [item['views'] for item in days] + [item['errands'] for item in days])
    for row in days:
        row['views_width'] = max(2, round(row['views'] * 100 / scale)) if row['views'] else 0
        row['errands_width'] = max(2, round(row['errands'] * 100 / scale)) if row['errands'] else 0
    context = {'query': query, 'answer': answer, 'conversation': conversation, 'categories': by_category, 'days': days, 'reads': reads, 'errands_open': errands_open, 'errands_taken': errands_taken, 'errands_posted': errands_posted, 'errands_done': errands_done, 'likes': action_counts.get('post_like', 0), 'favorites': action_counts.get('post_favorite', 0), 'popular': popular, 'order_count': task.objects.filter(Q(owner=request.user) | Q(runner=request.user)).count()}
    return render(request, '个人信息/ai.html', context)
