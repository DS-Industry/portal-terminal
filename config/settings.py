import os
import sys
import logging

from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv('SECRET_KEY', 'default-key')
DEBUG = os.getenv("DEBUG", "False") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,*").split(",")
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "False") == "True"

ASGI_APPLICATION = 'config.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(os.getenv('REDIS_HOST', 'redis'),
                      int(os.getenv('REDIS_PORT', 6379)))],
        },
    },
}

if not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.0.97:5173",
        "http://192.168.0.97:8000",
    ]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'channels',
    'orders.apps.OrdersConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# SQLite по умолчанию
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# Для Docker+Postgres:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'db'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'ru-ru'

TIME_ZONE = 'Europe/Moscow'

USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Modbus TCP настройки для OWEN PLC
MODBUS_HOST = os.getenv('MODBUS_HOST', '192.168.53.120')
MODBUS_PORT = int(os.getenv('MODBUS_PORT', '502'))
MODBUS_TIMEOUT = int(os.getenv('MODBUS_TIMEOUT', '10'))

LOG_DIR = os.environ.get('LOG_DIR', os.path.join(BASE_DIR, 'logs'))
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'django.log'),
            'formatter': 'verbose',
        },
        'console_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'console.log'),
            'formatter': 'simple',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'FILTERED_CONSOLE': {
            'handlers': ['console_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


class FilteredStreamToLogger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.target_prefixes = [
            '[LOG]', '[LOYALTY]', '[QR]', '[VENDOTEK]',
            '[INIT]', '[PLC-PROGRAMS]', '[PLC-STATUS]',
            '[PLC]', '[DS]', '[PLC-PRICES]'
        ]

    def write(self, buf):
        if any(buf.startswith(prefix) for prefix in self.target_prefixes) and buf.strip():
            for line in buf.rstrip().splitlines():
                self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass


# Инициализация перехвата stdout
if not hasattr(sys, 'stdout_original'):
    sys.stdout_original = sys.stdout
    stdout_logger = logging.getLogger('FILTERED_CONSOLE')
    sys.stdout = FilteredStreamToLogger(stdout_logger, logging.INFO)
