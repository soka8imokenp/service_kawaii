import dj_database_url
import os
from pathlib import Path
from dotenv import load_dotenv

# 1. Загружаем переменные из .env
load_dotenv()

# Корень проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Безопасность и отладка
SECRET_KEY = 'django-insecure-super-puper-secret-key-sumire-chan-123'
DEBUG = os.getenv('DEBUG') == 'True'

ALLOWED_HOSTS = ['tg-feedback-bot-swxe.onrender.com', 'localhost', '127.0.0.1']

# 3. Приложения
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'feedback', # Твое приложение
]

# 4. Middleware
MIDDLEWARE = [    
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# 5. База данных (Render PostgreSQL + Local SQLite)
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600
    )
}

# 6. Валидация паролей
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# 7. Интернационализация (Оставляем UTC для глобальной работы)
LANGUAGE_CODE = 'uz' # Язык интерфейса по умолчанию (узбекский)
TIME_ZONE = 'UTC'    # База хранит всё в UTC
USE_I18N = True
USE_TZ = True        # Позволяет Django работать с часовыми поясами

# 8. Статика
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'feedback', 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Хранилище для Render (WhiteNoise)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 9. CSRF и безопасность (КРИТИЧНО ДЛЯ RENDER)
CSRF_TRUSTED_ORIGINS = [
    'https://tg-feedback-bot-swxe.onrender.com',
    'https://ca8e-82-215-121-205.ngrok-free.app'
]

# Чтобы Django понимал, что запрос пришел через защищенный прокси Render
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CORS_ALLOW_ALL_ORIGINS = True