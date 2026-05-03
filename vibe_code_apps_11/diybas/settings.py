from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=False)

SECRET_KEY = os.environ.get('DIY_BAS_SECRET_KEY', 'change-me-in-production')
DEBUG = os.environ.get('DJANGO_DEBUG', 'false').lower() in ('1', 'true', 'yes')
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bas',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'diybas.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'bas' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    }
]
WSGI_APPLICATION = 'diybas.wsgi.application'
ASGI_APPLICATION = 'diybas.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(BASE_DIR / 'data' / 'django.sqlite3'),
    }
    ,
    # Optional second database for time series data. In production this should
    # point at a TimescaleDB (PostgreSQL) container or host. The default
    # configuration reads from environment variables and falls back to
    # PostgreSQL on localhost. When the ``timeseries`` entry is missing
    # entirely Django will use the default database for ``TimeSeriesData``
    # records. See ``bas/db_router.py`` for routing logic.
    'timeseries': {
        'ENGINE': os.environ.get('DIY_BAS_TIMESERIES_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('DIY_BAS_TIMESERIES_NAME', 'diy_timeseries'),
        'USER': os.environ.get('DIY_BAS_TIMESERIES_USER', ''),
        'PASSWORD': os.environ.get('DIY_BAS_TIMESERIES_PASSWORD', ''),
        'HOST': os.environ.get('DIY_BAS_TIMESERIES_HOST', 'timescale'),
        'PORT': os.environ.get('DIY_BAS_TIMESERIES_PORT', '5432'),
    },
}

# Route the TimeSeriesData model to the timeseries database
DATABASE_ROUTERS = ['bas.db_router.TimeSeriesRouter']

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

LOGIN_URL = '/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.environ.get('DIY_BAS_SESSION_COOKIE_SAMESITE', 'Lax')
SESSION_COOKIE_SECURE = os.environ.get('DIY_BAS_SESSION_COOKIE_SECURE', 'false').lower() in ('1', 'true', 'yes')
SESSION_COOKIE_AGE = max(1, int(os.environ.get('DIY_BAS_SESSION_HOURS', '24'))) * 3600
SESSION_SAVE_EVERY_REQUEST = os.environ.get('DIY_BAS_SESSION_REFRESH_EACH_REQUEST', 'true').lower() in ('1', 'true', 'yes')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

