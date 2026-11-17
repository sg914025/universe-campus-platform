# Author: UniVerse Team
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0002_profile_hometown_city_profile_hometown_province')]
    operations = [
        migrations.AddField(
            model_name='profile', name='student_number',
            field=models.CharField(blank=True, db_index=True, default='', max_length=20, verbose_name='学号'),
        ),
        migrations.AddField(
            model_name='profile', name='must_change_password',
            field=models.BooleanField(default=False, verbose_name='首次登录需修改密码'),
        ),
    ]
