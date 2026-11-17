"""CSV student account import. Author: UniVerse Team."""
import csv
import io
import re

from django.contrib.auth.models import User
from django.db import transaction

from .models import Profile


HEADER_ALIASES = {
    'student_number': ('学号', 'student_number', 'student_id', 'username'),
    'full_name': ('姓名', 'name', 'full_name'),
    'gender': ('性别', 'gender'),
    'age': ('年龄', 'age'),
}
GENDERS = {'男': 'male', 'male': 'male', 'm': 'male', '女': 'female', 'female': 'female', 'f': 'female',
           '其他': 'other', 'other': 'other', '': 'other'}
STUDENT_NUMBER_RE = re.compile(r'^\d{6,20}$')


class StudentImportError(ValueError):
    pass


def _column(fieldnames, aliases):
    normalized = {str(name or '').strip().lower(): name for name in fieldnames or ()}
    for alias in aliases:
        if alias.lower() in normalized:
            return normalized[alias.lower()]
    return None


def parse_student_csv(upload):
    if upload.size > 2 * 1024 * 1024:
        raise StudentImportError('CSV 文件不能超过 2 MB。')
    try:
        text = upload.read().decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise StudentImportError('请使用 UTF-8 编码保存 CSV 文件。') from exc
    reader = csv.DictReader(io.StringIO(text))
    columns = {key: _column(reader.fieldnames, aliases) for key, aliases in HEADER_ALIASES.items()}
    if not columns['student_number'] or not columns['full_name']:
        raise StudentImportError('CSV 必须包含“学号”和“姓名”两列。')
    rows, errors, seen = [], [], set()
    for line_number, raw in enumerate(reader, start=2):
        number = str(raw.get(columns['student_number'], '') or '').strip()
        name = str(raw.get(columns['full_name'], '') or '').strip()
        gender_raw = str(raw.get(columns['gender'], '') or '').strip().lower() if columns['gender'] else ''
        age_raw = str(raw.get(columns['age'], '') or '').strip() if columns['age'] else ''
        if not number and not name:
            continue
        if not STUDENT_NUMBER_RE.fullmatch(number):
            errors.append(f'第 {line_number} 行：学号须为 6–20 位数字。')
        elif number in seen:
            errors.append(f'第 {line_number} 行：学号 {number} 在文件中重复。')
        elif not name or len(name) > 50:
            errors.append(f'第 {line_number} 行：姓名不能为空且不能超过 50 个字符。')
        elif gender_raw not in GENDERS:
            errors.append(f'第 {line_number} 行：性别应为男、女或其他。')
        elif age_raw and (not age_raw.isdigit() or not 0 <= int(age_raw) <= 120):
            errors.append(f'第 {line_number} 行：年龄须为 0–120 的整数。')
        else:
            seen.add(number)
            rows.append({'student_number': number, 'full_name': name, 'gender': GENDERS[gender_raw],
                         'age': int(age_raw) if age_raw else None})
        if len(rows) + len(errors) > 5000:
            raise StudentImportError('单次最多导入 5000 名学生。')
    if errors:
        suffix = f'；另有 {len(errors) - 10} 条错误' if len(errors) > 10 else ''
        raise StudentImportError('；'.join(errors[:10]) + suffix)
    if not rows:
        raise StudentImportError('CSV 中没有可导入的学生记录。')
    return rows


@transaction.atomic
def import_students(rows, batch=None, prepared_passwords=None):
    existing = set(User.objects.filter(username__in=[row['student_number'] for row in rows])
                   .values_list('username', flat=True))
    created = []
    for row in rows:
        number = row['student_number']
        if number in existing:
            continue
        user = User(username=number, first_name=row['full_name'], is_active=True)
        if prepared_passwords is None:user.set_password(number)
        else:
            if number not in prepared_passwords:raise StudentImportError('名单账号状态已变化，请重新预览后导入。')
            user.password=prepared_passwords[number]
        user.save()
        Profile.objects.create(user=user, student_number=number, full_name=row['full_name'],
                               gender=row['gender'], age=row['age'], must_change_password=True,
                               import_batch=batch)
        created.append(user)
    return created, len(rows) - len(created)


class StudentImportBusy(StudentImportError):
    pass

def _retry_locked(operation):
    from django.db import OperationalError
    import time
    for attempt in range(3):
        try:return operation()
        except OperationalError as error:
            if not any(word in str(error).lower() for word in ('locked','busy')):raise
            if attempt==2:raise StudentImportBusy('当前数据库繁忙，本批次尚未导入，请稍后重试。') from error
            time.sleep(.1*(attempt+1))

@transaction.atomic
def _commit_batch(pk,actor,passwords):
    from django.db.models import F
    from django.utils import timezone
    from campus.audit import record_event
    from .models import StudentImportBatch
    # First statement is a write: reserve SQLite's writer before any read snapshot.
    if not StudentImportBatch.objects.filter(pk=pk).update(status=F('status')):raise StudentImportError('导入批次不存在。')
    batch=StudentImportBatch.objects.select_for_update().get(pk=pk)
    if batch.status=='imported':return batch,[],batch.skipped_count,True
    if batch.status!='preview':raise StudentImportError('该导入批次已撤销，不能再次导入。')
    created,skipped=import_students(batch.preview_rows,batch=batch,prepared_passwords=passwords)
    batch.status='imported';batch.created_count=len(created);batch.skipped_count=skipped;batch.imported_at=timezone.now();batch.preview_rows=[]
    batch.save(update_fields=['status','created_count','skipped_count','imported_at','preview_rows'])
    record_event(actor,'superadmin','确认导入学生账号',batch)
    return batch,created,skipped,False

def confirm_batch(pk,actor):
    from django.contrib.auth.hashers import make_password
    from .models import StudentImportBatch
    batch=_retry_locked(lambda:StudentImportBatch.objects.filter(pk=pk).first())
    if batch is None:raise StudentImportError('导入批次不存在。')
    if batch.status=='imported':return batch,[],batch.skipped_count,True
    if batch.status!='preview':raise StudentImportError('该导入批次已撤销，不能再次导入。')
    # Password hashing is expensive. Do it before taking a database write lock.
    existing=_retry_locked(lambda:set(User.objects.filter(username__in=[row['student_number'] for row in batch.preview_rows]).values_list('username',flat=True)))
    passwords={row['student_number']:make_password(row['student_number']) for row in batch.preview_rows if row['student_number'] not in existing}
    return _retry_locked(lambda:_commit_batch(pk,actor,passwords))
