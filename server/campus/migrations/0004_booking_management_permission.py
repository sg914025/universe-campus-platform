from django.conf import settings
from django.db import migrations


def preserve_existing_managers(apps, schema_editor):
    alias = schema_editor.connection.alias
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model(settings.AUTH_USER_MODEL)
    content_type, _ = ContentType.objects.using(alias).get_or_create(app_label='campus', model='importedcampususer')
    permission, _ = Permission.objects.using(alias).get_or_create(content_type=content_type, codename='manage_bookings', defaults={'name': '管理校园场地预约'})
    # Existing forum/errand managers previously managed bookings too. Preserve
    # that access once; newly assigned roles can be granted separately.
    for group in Group.objects.using(alias).filter(permissions__content_type__app_label='campus', permissions__codename='manage_campus'):
        group.permissions.add(permission)
    for user in User.objects.using(alias).filter(user_permissions__content_type__app_label='campus', user_permissions__codename='manage_campus'):
        user.user_permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [('campus', '0003_example_venues'), ('auth', '0012_alter_user_first_name_max_length'), ('contenttypes', '0002_remove_content_type_name')]
    operations = [
        migrations.AlterModelOptions(name='importedcampususer', options={'permissions': [('manage_campus', '管理校园论坛和跑腿'), ('manage_bookings', '管理校园场地预约')]}),
        migrations.RunPython(preserve_existing_managers, migrations.RunPython.noop),
    ]
