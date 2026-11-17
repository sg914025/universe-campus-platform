from django.db import migrations

def seed(apps,schema_editor):
    Venue=apps.get_model('campus','Venue')
    if Venue.objects.exists():return
    for number in range(1,5):
        Venue.objects.create(name=f'自习室 · {number:02d} 号座位',kind='study',location='示例自习区域',description='适合安静自习，每次预约一个座位，按两小时时段使用。',is_demo=True)
    Venue.objects.create(name='篮球场 · 示例半场',kind='basketball',location='示例运动区域',description='按半场预约，同一时段只保留一条预约。',is_demo=True)
    Venue.objects.create(name='羽毛球场 · 示例 1 号场',kind='badminton',location='示例运动区域',description='按场地预约，同一时段只保留一条预约。',is_demo=True)

class Migration(migrations.Migration):
    dependencies=[('campus','0002_venue_venuebooking')]
    operations=[migrations.RunPython(seed,migrations.RunPython.noop)]
