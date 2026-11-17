from django.db import migrations


def seed(apps,schema_editor):
    Department=apps.get_model('triage','Department')
    Consultation=apps.get_model('triage','Consultation')
    rows=[('general','全科医学科'),('neuro','神经内科'),('resp','呼吸内科'),('digest','消化内科'),('skin','皮肤科'),('bone','骨科'),('ent','耳鼻喉科'),('eye','眼科'),('child','儿科'),('urgent','急诊科')]
    mapping={slug:Department.objects.get_or_create(slug=slug,defaults={'name':name})[0].pk for slug,name in rows}
    for record in Consultation.objects.filter(department__isnull=True):
        slug='urgent' if record.emergency else 'neuro' if record.part=='head' else 'resp' if record.part=='chest' else 'digest' if record.part=='abdomen' else 'bone' if record.part.endswith(('_leg','_arm','_hand')) or record.part in ('back','legs','arms','hands') else 'general'
        record.department_id=mapping[slug];record.save(update_fields=['department'])


class Migration(migrations.Migration):
    dependencies=[('triage','0003_department_consultation_ai_report_and_more')]
    operations=[migrations.RunPython(seed,migrations.RunPython.noop)]
