"""校园诊室导航；时间统一使用上海时区，不读取访客电脑时间。"""
from zoneinfo import ZoneInfo
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

ROOMS = (
    ('room1', '诊室1', '普通诊室', '日常不适与一般健康咨询。', 'cross'),
    ('room2', '诊室2', '普通诊室', '日常不适与一般健康咨询。', 'heart'),
    ('room3', '诊室3', '普通诊室', '日常不适与一般健康咨询。', 'body'),
    ('emergency1', '急诊1', '急诊', '夜间及紧急情况，请联系现场值班医护。', 'cross'),
    ('emergency2', '急诊2', '急诊', '夜间及紧急情况，请联系现场值班医护。', 'heart'),
    ('special', '特殊通道', '特殊通道', '行动不便或需要协助时，请联系现场值班人员。', 'shield'),
)


def room_status(now=None):
    local = timezone.localtime(now or timezone.now(), ZoneInfo('Asia/Shanghai'))
    evening = local.hour >= 17
    return {'after_hours': evening, 'server_time': local.isoformat(), 'rooms': [
        {'id': key, 'name': name, 'category': category, 'desc': desc, 'icon': icon,
         'available': not evening or category == '急诊'}
        for key, name, category, desc, icon in ROOMS
    ]}


@never_cache
@require_GET
def availability(request):
    from .views import access_error
    error = access_error(request)
    return error if error is not None else JsonResponse(room_status())
