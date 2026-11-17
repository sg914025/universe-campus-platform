import os
import secrets
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Create the first campus super administrator only if none exists.'

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True, is_active=True).exists():
            self.stdout.write('An active super administrator already exists; no credentials changed.')
            return
        username = 'campus_root'
        while User.objects.filter(username__iexact=username).exists():
            username = 'campus_root_' + secrets.token_hex(3)
        password = 'Campus!' + secrets.token_urlsafe(20)
        directory = settings.BASE_DIR / 'private_credentials'
        directory.mkdir(exist_ok=True)
        path = directory / ('总管理员初始账号-' + secrets.token_hex(4) + '.txt')
        # Credentials are never printed, exposed through static/media, or reset
        # on subsequent runs. Database creation and file writing succeed together.
        try:
            with transaction.atomic():
                User.objects.create_superuser(username=username, password=password, first_name='总管理员')
                with path.open('x', encoding='utf-8') as stream:
                    stream.write('寰校通 UniVerse总管理员\n登录地址：http://127.0.0.1:8000/management/login/superadmin/\n账号：' + username + '\n初始密码：' + password + '\n\n请妥善保存，此文件不要提交到仓库或分享。\n')
        except Exception:
            if path.exists():
                path.unlink()
            raise
        self.stdout.write('First super administrator created. Credentials saved locally in private_credentials; never printed.')
