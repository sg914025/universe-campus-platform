from django.apps import AppConfig

class CampusConfig(AppConfig):
    default_auto_field='django.db.models.BigAutoField'
    name='campus'

    def ready(self):
        from . import security_events
        from django.contrib.auth import get_user_model
        # 校园管理权限不授予医疗后台或 Django 管理员权限。
        get_user_model().is_campus_manager=property(lambda user:user.is_active and user.has_perm('campus.manage_campus'))
        get_user_model().is_booking_manager=property(lambda user:user.is_active and user.has_perm('campus.manage_bookings'))
        from django.contrib.auth.models import AnonymousUser
        AnonymousUser.is_campus_manager=property(lambda user:False)
        AnonymousUser.is_booking_manager=property(lambda user:False)

        import os,sys
        if 'runserver' in sys.argv and (os.environ.get('RUN_MAIN')=='true' or '--noreload' in sys.argv):
            from .attendance import start_worker
            start_worker()
