"""Shared publication-time word rules. Existing risk signals still go to review."""
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata
from django.core.exceptions import ImproperlyConfigured

RULES=Path(__file__).with_name('blocked-terms.json')
ERROR='内容包含违规词，请修改后再发布。'
HAN=re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')

def normalize(value,compact=False):
    text=unicodedata.normalize('NFKC',str(value)).casefold().replace('ё','е')
    text=''.join(c for c in text if unicodedata.category(c)!='Cf')
    if compact:
        return ''.join(c for c in text if c.isalnum())
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in text).split())

@lru_cache(maxsize=1)
def load_rules(modified):
    data=json.loads(RULES.read_text(encoding='utf-8'))
    rows=data.get('rules',[])
    if not rows or any(not isinstance(row,dict) or not isinstance(row.get('term'),str) or not normalize(row['term']) for row in rows):
        raise ImproperlyConfigured('Invalid publication word rules')
    return tuple((normalize(row['term'],bool(HAN.search(row['term']))),bool(HAN.search(row['term']))) for row in rows)

def contains_blocked(value):
    if not value:return False
    spaced=normalize(value);compact=normalize(value,True)
    for term,is_han in load_rules(RULES.stat().st_mtime_ns):
        if is_han and term in compact:return True
        # Word boundaries prevent matching an innocent word's interior.
        if not is_han and re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',spaced):return True
    return False

class PublicationPolicyMixin:
    policy_fields=()
    def clean(self):
        data=super().clean()
        for field in self.policy_fields:
            value=data.get(field)
            # Tags are checked separately so adjoining innocent tags do not form a banned word.
            values=value if isinstance(value,(list,tuple)) else [value]
            if any(contains_blocked(item) for item in values):
                self.add_error(field,ERROR)
        return data
