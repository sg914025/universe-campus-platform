from django.db import migrations,models

class Migration(migrations.Migration):
    dependencies=[('campus','0010_ai_invocations')]
    operations=[migrations.AddField(model_name='venue',name='building',field=models.CharField('楼栋',max_length=16,choices=[('A','A 楼'),('B','B 楼'),('C','C 楼'),('library','图书馆'),('other','其他楼栋')],default='other',help_text='自习室所属楼栋；运动场地可保持其他楼栋。'))]
