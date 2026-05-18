from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Подключаем все пути из нашего приложения feedback
    path('feedback/', include('feedback.urls')), 
]