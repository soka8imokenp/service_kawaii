from django.urls import path
from . import views

app_name = 'feedback'

urlpatterns = [
    # Наш новый API-эндпоинт для Сумирэ
    path('api/send/', views.api_send_message, name='api_send_message'),
]