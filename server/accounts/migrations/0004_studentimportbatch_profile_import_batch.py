# Author: UniVerse Team
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('accounts', '0003_profile_student_account_fields'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='StudentImportBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('original_filename', models.CharField(max_length=255, verbose_name='原文件名')),
                ('preview_rows', models.JSONField(blank=True, default=list, verbose_name='待导入数据')),
                ('status', models.CharField(choices=[('preview', '待确认'), ('imported', '已导入'), ('rolled_back', '已撤销')], default='preview', max_length=20, verbose_name='状态')),
                ('total_count', models.PositiveIntegerField(default=0, verbose_name='名单数量')),
                ('created_count', models.PositiveIntegerField(default=0, verbose_name='新增数量')),
                ('skipped_count', models.PositiveIntegerField(default=0, verbose_name='跳过数量')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('imported_at', models.DateTimeField(blank=True, null=True, verbose_name='导入时间')),
                ('rolled_back_at', models.DateTimeField(blank=True, null=True, verbose_name='撤销时间')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='student_import_batches', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddField(
            model_name='profile', name='import_batch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_profiles', to='accounts.studentimportbatch'),
        ),
    ]
