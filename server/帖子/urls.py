from django.urls import path
from . import views
urlpatterns = [
    path('new/', views.create, name='post_create'),
    path('<int:pk>/like/', views.toggle_like, name='like'),
    path('<int:pk>/report/', views.report_post, name='report'),
    path('<int:pk>/favorite/', views.toggle_favorite, name='favorite'),
    path('<int:pk>/', views.detail, name='post_detail'),
    path('<int:pk>/edit/', views.edit, name='post_edit'),
    path('<int:pk>/delete/', views.delete, name='post_delete'),
]
