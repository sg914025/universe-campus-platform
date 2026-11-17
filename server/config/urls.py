from django.urls import path, include
from django.contrib import admin
from accounts import views
from triage import views as triage_views
from triage import doctor_views
from campus import views as campus_views
from campus import management_views
from campus import services
from campus import newcomer, staff_overview, task_assistant
from campus import home_weather
from campus import security_views
from triage.room_reservations import availability, reserve, mine, cancel
from triage.report_translation import translate as translate_report

from mobile_api import views as mobile_views

urlpatterns = [
    path('api/mobile/v1/', include('mobile_api.urls')),
    path('mobile/bridge/<str:ticket>/',mobile_views.bridge),
    path('m/',mobile_views.web,name='mobile-web'),
    path('m/<path:asset>',mobile_views.web),
    *[path('management/security/'+('' if section=='overview' else section+'/'),security_views.page,{'section':section},name='security-'+section) for section in ('overview','twin','risks','database','daily','ai')],
    path('management/security/check/',security_views.check,name='security-check'),
    path('management/security/backups/create/',security_views.backup,name='security-backup'),
    path('management/security/database/inspect/',security_views.inspect,name='security-database-inspect'),
    path('management/security/backups/<uuid:pk>/rehearse/',security_views.rehearse,name='security-rehearse'),
    path('management/security/backups/<uuid:pk>/verify/',security_views.verify,name='security-verify'),
    path('management/security/risks/<int:pk>/track/',security_views.track,name='security-track'),
    path('api/home/weather/',home_weather.api,name='home-weather'),
    path('assistant/', task_assistant.index, name='task-assistant'),
    path('api/assistant/state/', task_assistant.state, name='task-assistant-state'),
    path('api/assistant/chat/', task_assistant.chat, name='task-assistant-chat'),
    path('api/assistant/confirm/', task_assistant.confirm, name='task-assistant-confirm'),
    path('welcome/', newcomer.welcome, name='welcome'),
    path('management/overview/', staff_overview.overview, name='staff-overview'),
    path('management/audit/', staff_overview.audit_log, name='staff-audit'),
    path('my-services/', services.index, name='my-services'),
    path('api/services/unread/', services.count, name='service-unread'),
    path('my-services/read/', services.read, name='service-notice-read'),
    path('api/rooms/', availability, name='room-availability'),
    path('api/rooms/reserve/', reserve, name='room-reserve'),
    path('api/rooms/mine/', mine, name='room-mine'),
    path('api/rooms/<int:pk>/cancel/', cancel, name='room-cancel'),
    path('', campus_views.home, name='home'),
    path('management/accounts/', management_views.accounts, name='management-accounts'),
    path('management/accounts/template.csv', management_views.student_csv_template, name='student-csv-template'),
    path('management/accounts/activation-cards/', management_views.student_activation_cards, name='student-activation-cards'),
    path('management/accounts/activation-cards/<int:pk>.png', management_views.student_activation_qr, name='student-activation-qr'),
    path('management/accounts/import/<int:pk>/confirm/', management_views.confirm_student_import, name='student-import-confirm'),
    path('management/accounts/import/<int:pk>/rollback/', management_views.rollback_student_import, name='student-import-rollback'),
    path('management/accounts/students/<int:pk>/action/', management_views.student_account_action, name='student-account-action'),
    path('management/', management_views.portal, name='management'),
    path('management/login/<slug:role>/', management_views.sign_in, name='management-login'),
    path('management/logout/', management_views.sign_out, name='management-logout'),
    path('language/', management_views.language, name='ui-language'),
    path('guide/', views.guide, name='guide'),
    path('', include(('campus.urls', 'campus'), namespace='campus')),
    path('register/', views.register, name='register'),
    path('login/', views.sign_in, name='login'),
    *[path('login/'+module+'/', views.sign_in, {'module':module}, name=module+'-login') for module in ('forum','errands','guide','booking')],
    *[path('register/'+module+'/', views.register, {'module':module}, name=module+'-register') for module in ('forum','errands','guide','booking')],
    path('logout/', views.sign_out, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('password/change/', views.password_change, name='password-change'),
    path('activate/<str:token>/', views.activate, name='student-activate'),
    path('api/advanced/assess/', triage_views.assess, name='advanced-assess'),
    path('api/advanced/followup/', triage_views.followup, name='advanced-followup'),
    path('api/advanced/status/', triage_views.ai_status, name='advanced-status'),
    path('api/inbox/', triage_views.inbox, name='inbox'),
    path('api/report-translation/', translate_report, name='report-translation'),
    path('api/inbox/<int:pk>/read/', triage_views.read_reply, name='read-reply'),
    path('doctor/login/', doctor_views.sign_in, name='doctor-login'),
    path('doctor/', doctor_views.dashboard, name='doctor-dashboard'),
    path('doctor/drugs/', doctor_views.drug_library, name='doctor-drugs'),
    path('doctor/drugs/<slug:drug_id>/', doctor_views.drug_detail, name='doctor-drug-detail'),
    path('doctor/knowledge/', doctor_views.knowledge_library, name='doctor-knowledge'),
    path('doctor/cases/<int:pk>/', doctor_views.case_detail, name='doctor-case'),
    path('doctor/cases/<int:pk>/reply/', doctor_views.reply, name='doctor-reply'),
    path('doctor/cases/<int:pk>/medication/', doctor_views.generate_medication, name='doctor-medication'),
    path('doctor/cases/<int:pk>/discuss/', doctor_views.discuss, name='doctor-discuss'),
    path('doctor/cases/<int:pk>/invite/', doctor_views.invite, name='doctor-invite'),
    path('doctor/invitations/<int:pk>/', doctor_views.respond_invitation, name='doctor-invitation'),
    path('doctor/invitations/<int:pk>/revoke/', doctor_views.revoke_invitation, name='doctor-revoke'),
    path('system-admin/', admin.site.urls),
]

from django.conf import settings
from django.conf.urls.static import static
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
