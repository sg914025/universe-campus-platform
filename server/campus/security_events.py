"""Minimal local event telemetry. No credentials, bodies, IPs or raw URLs."""
from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver
from django.db import DatabaseError,transaction
from .models import SecurityEvent

def record(kind,request=None,status=0):
    match=getattr(request,'resolver_match',None)
    route=(getattr(match,'view_name',None) or 'unmatched')[:100]
    try:
        with transaction.atomic():
            SecurityEvent.objects.create(kind=kind,route=route,method=getattr(request,'method','')[:12],status_code=status)
    except DatabaseError:
        # Security logging must not break login, error handlers or pre-migration startup.
        pass

@receiver(user_login_failed,dispatch_uid='campus-security-login-failed')
def failed_login(sender,request=None,**kwargs):record('login_failed',request,401)
