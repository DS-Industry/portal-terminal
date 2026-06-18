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
            'hosts': [{
                'host': os.getenv('REDIS_HOST', 'redis'),
                'port': int(os.getenv('REDIS_PORT', 6379)),
                'socket_timeout': None,
            }],
        },
    },
}

if not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.0.97:5173",
        "http://192.168.53.145:5173",
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

# S3 Log Upload Configuration
PORTAL_NUMBER = os.getenv('PORTAL_NUMBER')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET')
AWS_S3_ENDPOINT_URL = os.getenv('AWS_S3_ENDPOINT_URL')  # Custom S3 endpoint (e.g., https://s3.twcstorage.ru)
AWS_S3_REGION = os.getenv('AWS_S3_REGION', 'us-east-1')
S3_LOG_UPLOAD_INTERVAL = int(os.getenv('S3_LOG_UPLOAD_INTERVAL', '65'))  # Default: 65 seconds (1 minute 5 seconds)
ENABLE_S3_LOGS = os.getenv('ENABLE_S3_LOGS', 'True').lower() == 'true'

OPTI_BASE_URL = os.getenv("OPTI_BASE_URL")
OPTI_LOGIN = os.getenv("OPTI_LOGIN")
OPTI_PASSWORD = os.getenv("OPTI_PASSWORD")
OPTI_POI_ID = os.getenv("OPTI_POI_ID")
OPTI_SERVICE_ID = os.getenv("OPTI_SERVICE_ID")

# Check if S3 logging should be enabled
S3_LOGGING_ENABLED = (
    ENABLE_S3_LOGS and
    PORTAL_NUMBER and
    AWS_ACCESS_KEY_ID and
    AWS_SECRET_ACCESS_KEY and
    AWS_S3_BUCKET
)

# Import S3 handler if S3 logging is enabled
S3_HANDLER_AVAILABLE = False
if S3_LOGGING_ENABLED:
    try:
        from config.s3_log_handler import S3RotatingFileHandler
        S3_HANDLER_AVAILABLE = True
    except ImportError:
        S3_HANDLER_AVAILABLE = False

# Factory function for creating file handlers
def create_file_handler(filename, max_bytes, backup_count, formatter_name, level='INFO', **kwargs):
    """Factory function to create file handler (S3 or regular)."""
    if S3_HANDLER_AVAILABLE:
        return S3RotatingFileHandler(
            filename=filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
            portal_number=PORTAL_NUMBER,
            s3_bucket=AWS_S3_BUCKET,
            s3_region=AWS_S3_REGION,
            s3_endpoint_url=AWS_S3_ENDPOINT_URL,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            upload_interval=S3_LOG_UPLOAD_INTERVAL,
        )
    else:
        return logging.handlers.RotatingFileHandler(
            filename=filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
        )

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
        # Ротация для основного лога Django (10MB, 5 файлов)
        # Использует S3RotatingFileHandler если S3 включен, иначе обычный RotatingFileHandler
        'file': {
            '()': lambda: create_file_handler(
                filename=os.path.join(LOG_DIR, 'django.log'),
                max_bytes=10 * 1024 * 1024,  # 10 MB
                backup_count=5,
                formatter_name='verbose',
                level='INFO'
            ),
            'level': 'INFO',
            'formatter': 'verbose',
        },

        # Ротация для console логов (10MB, 5 файлов)
        'console_file': {
            '()': lambda: create_file_handler(
                filename=os.path.join(LOG_DIR, 'console.log'),
                max_bytes=10 * 1024 * 1024,  # 10 MB
                backup_count=5,
                formatter_name='simple',
                level='INFO'
            ),
            'level': 'INFO',
            'formatter': 'simple',
        },

        # Вывод в консоль Docker
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },

        # Лог для ошибок (5MB, 3 файла)
        'error_file': {
            '()': lambda: create_file_handler(
                filename=os.path.join(LOG_DIR, 'errors.log'),
                max_bytes=5 * 1024 * 1024,  # 5 MB
                backup_count=3,
                formatter_name='verbose',
                level='ERROR'
            ),
            'level': 'ERROR',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['error_file', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'channels': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'orders': {
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
            '[PLC]', '[DS]', '[PLC-PRICES]', '[BILL-HOLDER]', '[WASH]', '[WEB-SOCKET]', '[DEBUG]'
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
