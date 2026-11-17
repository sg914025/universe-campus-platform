from django.contrib import admin
from django.utils import timezone

from .models import Consultation, Department, DoctorProfile, RoomAppointment
from .parts import PARTS


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('code', 'patient_name', 'body_part', 'status', 'emergency', 'created_at')
    list_filter = ('status', 'emergency')
    search_fields = ('user__username', 'user__guide_profile__full_name', 'description')
    readonly_fields = ('code', 'patient_info', 'body_part', 'detail', 'description', 'followup_answers', 'department', 'ai_report', 'duration',
                       'feeling', 'level', 'emergency', 'status', 'created_at', 'replied_by', 'replied_at', 'reply_read')
    fields = ('code', 'patient_info', 'body_part', 'detail', 'description', 'followup_answers', 'department', 'ai_report', 'duration', 'feeling',
              'level', 'emergency', 'status', 'created_at', 'doctor_reply', 'replied_by', 'replied_at', 'reply_read')

    @admin.display(description='用户')
    def patient_name(self, obj):
        profile = getattr(obj.user, 'guide_profile', None)
        return profile.full_name if profile else obj.user.username

    @admin.display(description='注册资料')
    def patient_info(self, obj):
        profile = getattr(obj.user, 'guide_profile', None)
        if not profile:
            return obj.user.username
        age = f'{profile.age} 岁' if profile.age is not None else '年龄未填'
        return f'{profile.full_name} / {profile.get_gender_display()} / {age} / 账号：{obj.user.username}'

    @admin.display(description='部位')
    def body_part(self, obj):
        return PARTS.get(obj.part, {}).get('name', obj.part)

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        doctor = DoctorProfile.objects.filter(user=request.user,active=True,department__active=True).first()
        if doctor is None:
            return queryset.none()
        from .doctor_views import visible_consultations
        return queryset.filter(pk__in=visible_consultations(doctor).values('pk'))

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if 'doctor_reply' in form.changed_data:
            obj.doctor_reply = obj.doctor_reply.strip()
            obj.status = 'replied' if obj.doctor_reply else 'pending'
            obj.replied_by = request.user if obj.doctor_reply else None
            obj.replied_at = timezone.now() if obj.doctor_reply else None
            obj.reply_read = False
        super().save_model(request, obj, form, change)


admin.site.site_header = '安心导诊 · 系统管理'
admin.site.site_title = '系统管理'
admin.site.index_title = '账号、科室与咨询管理'

# 系统管理员负责分配医生所属科室；患者不能自行注册为医生。
admin.site.register(Department)
admin.site.register(DoctorProfile)


@admin.register(RoomAppointment)
class RoomAppointmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'user', 'room', 'starts_at', 'number', 'status')
    list_filter = ('room', 'status', 'starts_at')
    search_fields = ('user__username', 'user__guide_profile__full_name')
    readonly_fields = ('user', 'room', 'starts_at', 'ends_at', 'number', 'request_key', 'status', 'created_at', 'cancelled_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
