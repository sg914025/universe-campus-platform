from django.core.paginator import Paginator
from django.db.models import Q, Count, Max, F
from django.db.models.functions import Greatest
from django.utils.dateparse import parse_datetime
from django.shortcuts import render
from 帖子.models import post, categories, history, comment, tag, announcement

def index(request, section='home'):
    sections = {
        'home': ('校园广场', '在这里，遇见校园里的你。', '分享学习经验，聊聊校园生活，让每一个问题都有人回应。', None),
        'daily': ('日常', '记录校园里的小日常。', '聊聊食堂、课堂和课余生活，分享今天发生的小事。', ['日常', '校园生活']),
        'help': ('求助', '遇到问题，一起想办法。', '学习问题、失物寻找和校园疑问，都可以在这里问问。', ['求助', '学习交流', '失物招领']),
        'friends': ('交友', '认识一起学习和玩耍的朋友。', '找学习搭子、运动伙伴，认识兴趣相同的同学。', ['交友']),
    }
    section_title, hero_title, hero_description, section_categories = sections[section]
    visible_categories = categories
    if section_categories:
        visible_categories = [(value, label) for value, label in categories if value in section_categories]
    keyword = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    tag_slug = request.GET.get('tag', '').strip().casefold()
    sort = request.GET.get('sort', 'time')
    if sort not in ['hot', 'time', 'reply']:
        sort = 'time'
    posts = post.objects.filter(is_hidden=False).select_related('author').prefetch_related('tags').annotate(
        comment_count=Count('comments', filter=Q(comments__is_hidden=False), distinct=True), like_count=Count('likes', distinct=True),
        quote_count=Count('quotes', filter=Q(quotes__is_hidden=False), distinct=True),
        favorite_count=Count('favorite', distinct=True), latest_reply=Max('comments__created_at', filter=Q(comments__is_hidden=False)),
    ).annotate(score=F('like_count') * 2 + F('comment_count') * 3 + F('quote_count') * 4 + F('favorite_count') * 2 + F('view_count'))
    if section_categories:
        posts = posts.filter(category__in=section_categories)
    if keyword:
        posts = posts.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))
    if category:
        posts = posts.filter(category=category)
    if tag_slug:
        posts = posts.filter(tags__slug=tag_slug)
    if sort == 'hot':
        posts = posts.order_by('-score', '-created_at', '-pk')
    elif sort == 'reply':
        posts = posts.order_by(F('latest_reply').desc(nulls_last=True), '-created_at', '-pk')
    else:
        posts = posts.order_by('-created_at', '-pk')
    page = Paginator(posts, 8).get_page(request.GET.get('page'))
    ids = [item.pk for item in page]
    if request.user.is_authenticated:
        seen = dict(history.objects.filter(user=request.user, post_id__in=ids).values_list('post_id', 'viewed_at'))
    else:
        seen = {int(key): parse_datetime(value) for key, value in request.session.get('seen_posts', {}).items()}
    for item in page:
        last_activity = max(item.updated_at, item.latest_reply or item.updated_at)
        item.is_seen = item.pk in seen and seen[item.pk] is not None and seen[item.pk] >= last_activity
    recent_replies = comment.objects.filter(post__is_hidden=False, is_hidden=False).select_related('post', 'author', 'author__profile').order_by('-created_at', '-pk')[:6]
    popular_tags = tag.objects.annotate(post_count=Count('posts', filter=Q(posts__is_hidden=False), distinct=True)).filter(post_count__gt=0).order_by('-post_count', 'name')[:12]
    pinned_announcements = announcement.objects.filter(is_active=True)[:5] if section == 'home' else announcement.objects.none()
    return render(request, '主页/index.html', {'announcements': pinned_announcements, 'page': page, 'keyword': keyword, 'category': category, 'tag_slug': tag_slug, 'popular_tags': popular_tags, 'categories': visible_categories, 'section': section, 'section_title': section_title, 'hero_title': hero_title, 'hero_description': hero_description, 'sort': sort, 'recent_replies': recent_replies})
