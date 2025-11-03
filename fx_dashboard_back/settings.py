import os
from pathlib import Path
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-your-secret-key-here')

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',  # CORS support
    'exchange',  # our app
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS middleware 
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'fx_dashboard_back.urls'

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

WSGI_APPLICATION = 'fx_dashboard_back.wsgi.application'

  # PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'fxdb'),
        'USER': os.environ.get('POSTGRES_USER', 'fxuser'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'fxpass123'),
        'HOST': os.environ.get('POSTGRES_HOST', '127.0.0.1'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# CORS settings - allow frontend to access API
CORS_ALLOWED_ORIGINS = [
    "https://famous-trifle-b3b58e.netlify.app",
]

# Allow credentials (cookies, authorization headers, etc.)
CORS_ALLOW_CREDENTIALS = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django cache settings - Redis
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100,
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'fx',
        'TIMEOUT': 300,
    }
}

# Per-feature cache timeouts (in seconds)
CACHE_TIMEOUT = {
    'currencies': 86400,      # 24 hours
    'time_series': 1800,     # 30 minutes
}

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/1')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Celery Beat Schedule - Run on 1st of every month at 2 AM UTC
CELERY_BEAT_SCHEDULE = {
    'fetch-last-month-data': {
        'task': 'exchange.tasks.fetch_last_month_data',
        'schedule': crontab(day_of_month=1, hour=2, minute=0),
    },
}