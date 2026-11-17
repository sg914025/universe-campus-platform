"""Deterministic critical-field comparison, NOT proof of full translation accuracy."""
import re,unicodedata
from datetime import timedelta
from .task_intent import rules

FIELDS={'day':'日期','time':'涉及时间','kind':'场地类型','people':'人数','negation':'否定或排除条件'}
def fields(text,today):
    text=unicodedata.normalize('NFKC',text).lower()
    parsed=rules(text,today);result={k:parsed[k] for k in ('day','kind') if k in parsed}
    absolute=re.search(r'\b(\d{1,2})[.](\d{1,2})[.](20\d{2})\b',text)
    if absolute:
        try:result['day']=today.replace(year=int(absolute[3]),month=int(absolute[2]),day=int(absolute[1])).isoformat()
        except ValueError:result['day']='invalid'
    weekdays=[('周一','星期一','monday','понедельник','月曜'),('周二','星期二','tuesday','вторник','火曜'),('周三','星期三','wednesday','среду','среда','水曜'),('周四','星期四','thursday','четверг','木曜'),('周五','星期五','friday','пятниц','金曜'),('周六','星期六','saturday','суббот','土曜'),('周日','周天','星期日','sunday','воскресень','日曜')]
    for i,terms in enumerate(weekdays):
        if any(term in text for term in terms) and 'day' not in result:result['day']=(today+timedelta(days=(i-today.weekday())%7)).isoformat()
    time=re.search(r'(?<!\d)([01]?\d|2[0-3]):([0-5]\d)',text)
    if time:result['time']=f'{int(time[1]):02d}:{time[2]}'
    elif parsed.get('slot') and parsed['slot']!='invalid':result['time']=parsed['slot']+':00'
    else:
        hour=re.search(r'(\d{1,2})\s*(?:点|時|час)',text)
        if hour:
            h=int(hour[1]);h+=12 if h<12 and parsed.get('period') in ('afternoon','evening') else 0
            result['time']=f'{h:02d}:00'
    count=re.search(r'(\d+)\s*(?:人|people|persons?|человек|чел\b)',text)
    if count:result['people']=count[1]
    negative=bool(re.search(r'不要|不能|不可|不想|除了|以外|除く|\bnot\b|\bexcept\b|\bwithout\b|\bне\b|кроме',text))
    result['negation']='yes' if negative else 'no'
    result['complex']=bool(re.search(r'下周|来週|next week|следующ|至少|最多|早于|晚于|\bafter\s+\d|\bbefore\s+\d|после\s+\d|до\s+\d|не раньше|не позже',text))
    return result

def compare(original,translation,today):
    left,right=fields(original,today),fields(translation,today)
    rows=[];conflicts=[];missing=[]
    for key,label in FIELDS.items():
        a,b=left.get(key),right.get(key)
        if a is None and b is None:continue
        state='match' if a==b and a!='invalid' else 'missing' if a is None or b is None else 'mismatch'
        display={'study':'自习室','basketball':'篮球场','badminton':'羽毛球场','yes':'检测到','no':'未检测到'}
        rows.append({'key':key,'label':label,'original':display.get(a,a) or '—','translated':display.get(b,b) or '—','state':state})
        if state=='mismatch':conflicts.append(key)
        elif state=='missing':missing.append(key)
    evidence=any(row['key']!='negation' and row['state']=='match' for row in rows)
    status='mismatch' if conflicts else 'review' if missing or not evidence or left['negation']=='yes' or left['complex'] or right['complex'] else 'aligned'
    return {'status':status,'rows':rows,'conflicts':conflicts,'limited':True}
