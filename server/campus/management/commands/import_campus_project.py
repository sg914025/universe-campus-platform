"""一次性复制旧论坛记录，保留密码哈希；不覆盖同名导诊账号。"""
from pathlib import Path
import sqlite3
from datetime import timezone as datetime_timezone
from django.utils.dateparse import parse_datetime
from django.apps import apps
from django.contrib.auth.models import User,Group,Permission
from django.core.management.base import BaseCommand,CommandError
from django.db import connection,transaction
from campus.models import ImportedCampusUser,CampusImportState

class Command(BaseCommand):
    def add_arguments(self,parser):
        parser.add_argument('--database',required=True)
        parser.add_argument('--report',required=True)

    def handle(self,*args,**options):
        source=Path(options['database']).resolve()
        key=str(source)
        if CampusImportState.objects.filter(source_key=key).exists():
            self.stdout.write('Campus data already imported; no changes.');return
        if not source.is_file():raise CommandError('Source database missing')
        original=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
        snapshot=sqlite3.connect(':memory:');original.backup(snapshot);original.close()
        snapshot.row_factory=sqlite3.Row
        tables={row[0] for row in snapshot.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        models=[model for label in ('帖子','跑腿') for model in apps.get_app_config(label).get_models(include_auto_created=True)]
        copied_tables=[];renamed=[]
        with connection.constraint_checks_disabled(),transaction.atomic():
            for model in models:
                if model._base_manager.exists():raise CommandError('Campus tables contain records; refusing to overwrite')
            group,_=Group.objects.get_or_create(name='campus_moderators')
            group.permissions.add(Permission.objects.get(content_type__app_label='campus',codename='manage_campus'))
            mapping={}
            for row in snapshot.execute('SELECT * FROM auth_user ORDER BY id'):
                name=row['username'].casefold();base=name;number=0
                while User.objects.filter(username__iexact=name).exists():
                    number+=1;name=base[:125]+'_campus'+(str(number) if number>1 else '')
                if name!=row['username']:renamed.append((row['username'],name))
                data={field.name:row[field.column] for field in User._meta.concrete_fields if field.name not in ('id','username','is_staff','is_superuser')}
                for date_field in ('date_joined','last_login'):
                    if data.get(date_field):
                        value=parse_datetime(data[date_field])
                        data[date_field]=value.replace(tzinfo=datetime_timezone.utc) if value.tzinfo is None else value
                user=User.objects.create(username=name,is_staff=False,is_superuser=False,**data)
                mapping[row['id']]=user.pk
                ImportedCampusUser.objects.create(source_id=row['id'],user=user)
                if row['is_staff'] or row['is_superuser']:user.groups.add(group)
            with connection.cursor() as cursor:
                for model in models:
                    table=model._meta.db_table
                    if table not in tables:continue
                    rows=list(snapshot.execute('SELECT * FROM "'+table+'"'))
                    if not rows:continue
                    columns=[field.column for field in model._meta.local_fields]
                    if any(column not in rows[0].keys() for column in columns):raise CommandError('Source schema differs: '+table)
                    foreign={row['from'] for row in snapshot.execute('PRAGMA foreign_key_list("'+table+'")') if row['table']=='auth_user'}
                    if table=='帖子_risk_alert':foreign.add('author_id')
                    values=[[mapping[row[column]] if column in foreign and row[column] is not None else row[column] for column in columns] for row in rows]
                    query='INSERT INTO '+connection.ops.quote_name(table)+' ('+','.join(connection.ops.quote_name(column) for column in columns)+') VALUES ('+','.join(['%s']*len(columns))+')'
                    cursor.executemany(query,values);copied_tables.append(table)
            connection.check_constraints(table_names=copied_tables)
            CampusImportState.objects.create(source_key=key)
        report=Path(options['report']);report.parent.mkdir(parents=True,exist_ok=True)
        lines=['校园账号迁移说明','旧论坛账号密码保持不变；同名账号单独保留，未合并医疗资料。','原论坛管理员仅保留校园管理权限，不获得医疗后台权限。','首次进入统一主页时，需要补充姓名、性别等导诊所需资料。','']
        lines += [old+' → '+new for old,new in renamed] or ['没有需要更名的账号。']
        report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        self.stdout.write(f'Imported {len(mapping)} campus users and {len(copied_tables)} data tables. Existing medical users preserved.')
