class CampusMembershipMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        if not request.user.is_authenticated and any(request.path == prefix.rstrip('/') or request.path.startswith(prefix) for prefix in ('/forum/','/errands/','/booking/')):
            from django.contrib.auth.views import redirect_to_login
            from django.urls import reverse
            from django.utils.cache import add_never_cache_headers
            module=request.path.strip('/').split('/')[0]
            response=redirect_to_login(request.get_full_path(),reverse(module+'-login'))
            add_never_cache_headers(response)
            return response
        if request.user.is_authenticated and request.method=='POST' and request.path.startswith(('/forum/','/errands/')):
            from 帖子.models import profile
            profile.objects.get_or_create(user=request.user)
        response=self.get_response(request)
        if response.status_code in (403,404) or response.status_code>=500:
            if not request.path.startswith(('/static/','/campus-media/')):
                from .security_events import record
                record('server_error' if response.status_code>=500 else 'permission_denied' if response.status_code==403 else 'not_found',request,response.status_code)
        if request.user.is_authenticated and request.path.startswith(('/forum/','/errands/','/campus-admin/')):
            from django.utils.cache import add_never_cache_headers
            add_never_cache_headers(response)
        return response


class SeatExpiryMiddleware:
    def __init__(self,get_response):self.get_response=get_response;self.last=0
    def __call__(self,request):
        import time
        from django.db import OperationalError,ProgrammingError
        if time.monotonic()-self.last>15:
            self.last=time.monotonic()
            try:
                from .booking_notices import process_attendance
                process_attendance()
            except (OperationalError,ProgrammingError):pass
        return self.get_response(request)
