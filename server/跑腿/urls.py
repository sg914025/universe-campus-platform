from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='errands'),
    path('new/', views.create, name='errand_create'),
    path('mine/', views.mine, name='errand_mine'),
    path('questions/', views.questions, name='errand_questions'),
    path('questions/<int:pk>/', views.question_detail, name='errand_question'),
    path('<int:pk>/', views.detail, name='errand_detail'),
    path('<int:pk>/take/', views.take, name='errand_take'),
    path('<int:pk>/cancel/', views.cancel, name='errand_cancel'),
    path('<int:pk>/deliver/', views.deliver, name='errand_deliver'),
    path('<int:pk>/complete/', views.complete, name='errand_complete'),
    path('<int:pk>/proof/', views.proof, name='errand_proof'),
]
