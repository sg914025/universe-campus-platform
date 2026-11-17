from django.urls import path,include
from accounts import views
from . import booking_views,journey_views,home_agenda,service_plans,campus_map

from . import friend_services

from . import notice_admin
from . import checkin_views
from . import map_inventory

urlpatterns=[
    path('campus-admin/booking-notices/',notice_admin.index,name='booking-notice-admin'),
    path('campus-admin/bookings/<int:pk>/release/',booking_views.release_seat,name='booking-release'),
    path('booking/<int:pk>/checkin/',checkin_views.checkin,name='booking-checkin'),
    path('booking/<int:pk>/qr/',checkin_views.qr,name='booking-qr'),
    path('booking/<int:pk>/navigate/',checkin_views.navigate,name='booking-navigate'),
    path('api/campus-map/inventory/',map_inventory.inventory,name='map-inventory'),
    path('friends/',friend_services.hub,name='friend-hub'),
    path('api/home/friends/',friend_services.roster,name='friend-roster'),
    path('friends/cards/<int:pk>/',friend_services.shared_card,name='friend-shared-card'),
    path('friends/messages/<int:pk>/translation/',friend_services.message_translation,name='friend-message-translation'),
    path('campus-map/',campus_map.index,name='campus-map'),
    path('api/assistant/plans/',service_plans.endpoint,name='service-plans'),
    path('api/home/agenda/',home_agenda.agenda,name='home-agenda'),
    path('campus-admin/waitlist/',journey_views.queue_admin,name='waitlist-admin'),
    path('api/assistant/preview/',journey_views.assistant_preview,name='assistant-preview'),
    path('journey/meaning/',journey_views.meaning_check,name='meaning-check'),
    path('journey/preview/<int:pk>/',journey_views.preview,name='booking-preview'),
    path('journey/confirm/',journey_views.commit,name='booking-commit'),
    path('journey/cards/<int:pk>/',journey_views.card,name='service-card'),
    path('journey/cards/<int:pk>/calendar/',journey_views.calendar,name='service-calendar'),
    path('booking/waitlist/',journey_views.queue,name='waitlist'),
    path('booking/waitlist/<int:pk>/join/',journey_views.join_queue,name='waitlist-join'),
    path('booking/',booking_views.index,name='booking'),
    path('booking/venues/<int:pk>/',booking_views.venue_detail,name='booking-venue'),
    path('booking/mine/',booking_views.mine,name='booking-mine'),
    path('booking/<int:pk>/cancel/',booking_views.cancel,name='booking-cancel'),
    path('campus-admin/bookings/',booking_views.management,name='booking-admin'),
    path('campus-admin/venues/<int:pk>/',booking_views.edit_venue,name='booking-venue-edit'),
    path('forum/',include('主页.urls')),
    path('forum/daily/',include('日常.urls')),
    path('forum/help/',include('求助.urls')),
    path('forum/friends/',include('交友.urls')),
    path('forum/posts/',include('帖子.urls')),
    path('forum/profile/',include('个人信息.urls')),
    path('errands/',include('跑腿.urls')),
    path('campus-admin/',include('后台管理.urls')),
    path('login/',views.sign_in,name='login'),
    path('register/',views.register,name='register'),
    path('logout/',views.sign_out,name='logout'),
]
