"""Inference request metrics only. Never store prompts, responses or account data."""
from contextlib import contextmanager
from time import perf_counter
from types import SimpleNamespace
import logging,re

@contextmanager
def measure(provider,model,enabled=True):
    state=SimpleNamespace(success=False)
    start=perf_counter()
    try:yield state
    finally:
        if enabled:
            try:
                from .models import AIInvocation
                safe=re.sub(r'[^a-zA-Z0-9._:/@+ -]','?',str(model))[:150]
                from django.db import transaction
                with transaction.atomic():AIInvocation.objects.create(provider=provider,model=safe,success=bool(state.success),duration_ms=min(86400000,max(0,round((perf_counter()-start)*1000))))
            except Exception:
                # Metrics must not make a completed answer fail, including migration/startup windows.
                logging.getLogger(__name__).warning('AI usage metric unavailable')
