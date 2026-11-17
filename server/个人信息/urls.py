from django.urls import path
from . import views
from campus import demo_payments
urlpatterns = [path('', views.info, name='profile'), path('ai/', views.ai_insights, name='ai_insights'), path('edit/', views.edit, name='profile_edit'),
    path('recharge/', demo_payments.index, name='recharge'),
    path('recharge/<uuid:pk>/',demo_payments.checkout,name='demo-checkout'),
    path('recharge/<uuid:pk>/complete/',demo_payments.complete,name='demo-payment-complete'),
    path('messages/', views.inbox, name='inbox'),
    path('messages/unread/', views.unread_messages, name='unread_messages'),
    path('member/<int:pk>/', views.member, name='member'),
    path('member/<int:pk>/follow/', views.toggle_follow, name='follow'),
    path('chat/<int:pk>/', views.chat, name='chat'),
    path('search/', views.user_search, name='user_search')]
