"""每个演示科室创建一个医生账号，密码只写入指定的本地 TXT。"""
import os
import secrets
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth.models import User
from django.db import transaction
from triage.models import Department,DoctorProfile
from triage.departments import DEPARTMENTS


class Command(BaseCommand):
    help='为每个科室创建一个演示医生账号，保存到本地 TXT，不覆盖已有账号或密码。'

    def add_arguments(self,parser):
        parser.add_argument('--output',required=True,help='账号 TXT 的本地绝对路径')

    def handle(self,*args,**options):
        output=Path(options['output']).resolve()
        output.parent.mkdir(parents=True,exist_ok=True)
        created=[]
        # 先检查目标文件，写文件失败会回滚新账号，防止丢失初始密码。
        with transaction.atomic():
            for slug,name in DEPARTMENTS:
                department,_=Department.objects.get_or_create(slug=slug,defaults={'name':name})
                username='doctor_'+slug
                user=User.objects.filter(username__iexact=username).first()
                if user:
                    if not DoctorProfile.objects.filter(user=user,department=department).exists():
                        raise CommandError('预设医生账号名已被其他账号使用，请管理员检查。')
                    continue
                password='Guide!'+secrets.token_urlsafe(15)
                user=User.objects.create_user(username=username,password=password,first_name=name+'演示医生',is_staff=False)
                DoctorProfile.objects.create(user=user,department=department,display_name=name+'演示医生')
                created.append((name,username,password))
            if not created:
                self.stdout.write('医生账号已存在，未修改密码或账号文件。')
                return
            lines=['安心导诊 · 演示医生账号','医生登录：http://127.0.0.1:8767/doctor/login/',
                   '每个科室一个演示账号，仅用于本地项目测试。请妥善保存此文件，不公开分享。',
                   '本科室咨询可直接查看；其他科室的会诊邀请接受后，只开放被邀请的那条咨询。',
                   '会诊讨论仅医生可见，正式回复发送到患者站内信箱。','']
            for name,username,password in created:
                lines.extend([name,'账号：'+username,'密码：'+password,''])
            try:
                with output.open('x',encoding='utf-8-sig') as stream:
                    stream.write('\n'.join(lines))
            except OSError as error:
                raise CommandError('账号文件已存在或不能写入；新账号已回滚，请指定新的文件名。') from error
        self.stdout.write(f'已创建 {len(created)} 个演示医生账号并写入指定 TXT（未显示密码）。')
