"""Audit successful persisted staff changes. Never store request bodies or clinical text."""
from functools import wraps
from django.apps import apps
from django.db import transaction
from .models import StaffAuditEvent

SAFE_STATE_FIELDS={'status','active','is_active','is_hidden','kind'}


def record_event(user,module,action,obj,changed=(),before=None,after=None):
    return StaffAuditEvent.objects.create(actor=user,actor_name=user.username,module=module,
        action=action,target=f'{obj._meta.label_lower}:{obj.pk}',changed_fields=list(changed),
        before_state={key:value for key,value in (before or {}).items() if key in SAFE_STATE_FIELDS},
        after_state={key:value for key,value in (after or {}).items() if key in SAFE_STATE_FIELDS})


def audit_change(role,model_label,fields,action):
    """Record actual field changes, including existing queryset.update workflows."""
    def decorate(view):
        @wraps(view)
        def wrapped(request,*args,**kwargs):
            from .management_views import has_role
            if request.method!='POST' or not has_role(request.user,role):
                return view(request,*args,**kwargs)
            model=apps.get_model(model_label)
            pk=kwargs.get('pk')
            with transaction.atomic():
                obj=model.objects.select_for_update().filter(pk=pk).first()
                before={field:getattr(obj,field) for field in fields} if obj else {}
                response=view(request,*args,**kwargs)
                if obj and response.status_code<400:
                    current=model.objects.filter(pk=pk).values(*fields).first()
                    if current is not None:
                        changed=[field for field in fields if before[field]!=current[field]]
                        if changed:record_event(request.user,role,action,obj,changed,before,current)
                return response
        return wrapped
    return decorate
