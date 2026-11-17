from django.contrib.auth import get_user_model
from 帖子.models import follow

def are_friends(user, target):
    return follow.objects.filter(user=user, target=target).exists() and follow.objects.filter(user=target, target=user).exists()

def friends_for(user):
    outgoing = follow.objects.filter(user=user).values_list('target_id', flat=True)
    incoming = follow.objects.filter(target=user).values_list('user_id', flat=True)
    return get_user_model().objects.filter(pk__in=outgoing).filter(pk__in=incoming).select_related('profile').order_by('username')

def unread_for(user):
    from 帖子.models import chat_message
    return chat_message.objects.filter(receiver=user, sender__in=friends_for(user), is_read=False)
