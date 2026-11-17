"""Require imported students to replace their initial password. Author: UniVerse Team."""
from django.shortcuts import redirect
from django.urls import reverse


class InitialPasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_staff and not request.user.is_superuser:
            profile = getattr(request.user, 'guide_profile', None)
            if profile and profile.must_change_password:
                allowed = {reverse('password-change'), reverse('logout'), reverse('ui-language')}
                if request.path not in allowed and not request.path.startswith(('/static/', '/campus-media/', '/api/mobile/v1/', '/m/')):
                    return redirect('password-change')
        return self.get_response(request)
