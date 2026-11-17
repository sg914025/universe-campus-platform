from .social import friends_for, unread_for

def friend_panel(request):
    # 管理后台使用独立导航，不需要每个后台页面都查询好友和未读消息。
    if request.user.is_authenticated and not request.user.is_campus_manager:
        from 跑腿.models import question
        return {'sidebar_friends': friends_for(request.user), 'unread_count': unread_for(request.user).count() + question.objects.filter(user=request.user, reply_unread=True).count()}
    return {'sidebar_friends': [], 'unread_count': 0}
