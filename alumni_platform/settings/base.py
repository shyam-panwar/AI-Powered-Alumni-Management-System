from pathlib import Path
from datetime import timedelta
from decouple import config

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-in-production')

# Application definition
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'channels',
    'django_celery_beat',

    'imagekit',
    'taggit',
    
    # Custom apps
    'apps.accounts',
    'apps.feed',
    'apps.sessions_app',
    'apps.referrals',
    'apps.payments',
    'apps.ai_tools',
    'apps.dashboard',
    'apps.notifications',
    'apps.ratings',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'utils.middleware.JWTAuthMiddleware',
]

ROOT_URLCONF = 'alumni_platform.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'utils.context_processors.user_context',
                'utils.context_processors.cache_bust',
            ],
        },
    },
]

WSGI_APPLICATION = 'alumni_platform.wsgi.application'
ASGI_APPLICATION = 'alumni_platform.asgi.application'

# Password validation
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

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# REST Framework Configuration
# NOTE: DEFAULT_THROTTLE_CLASSES is intentionally empty here.
# Throttling requires a cache backend (Redis). dev.py and prod.py enable it
# only when Redis is confirmed available, to avoid connection errors at startup.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'utils.authentication.JWTCookieAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
    },
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS Settings
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

CORS_ALLOW_CREDENTIALS = True

# Celery Configuration
# NOTE: CELERY_BROKER_URL and CELERY_RESULT_BACKEND are intentionally NOT set here.
# Setting them to redis://localhost:6379 as a default causes connection errors on
# any environment without Redis. dev.py and prod.py define these based on environment.
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Channel Layers (WebSocket)
# NOTE: CHANNEL_LAYERS is intentionally NOT set here.
# channels_redis requires a live Redis connection at startup. A localhost default
# causes crashes on environments without Redis.
# dev.py uses InMemoryChannelLayer; prod.py configures based on REDIS_URL.

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('EMAIL_HOST_USER', default='noreply@alumniconnect.com')
EMAIL_TIMEOUT = 15  # seconds

# Demo OTP bypass — @test.com accounts accept this fixed code instead of email OTP
# Set to empty string '' to disable the bypass in production
DEMO_OTP = config('DEMO_OTP', default='')

# Groq API (AI Career Tools — resume scorer, builder, interview, skill gap)
GROQ_API_KEY = config('GROQ_API_KEY', default='')
GROQ_MODEL   = 'llama-3.3-70b-versatile'   # Free tier, fast, high quality

# Gemini Configuration (resume parsing + AI summary)
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_MODEL = 'gemini-2.0-flash'

# Affinda Configuration (Alternate resume parsing)
AFFINDA_API_KEY = config('AFFINDA_API_KEY', default='')
AFFINDA_WORKSPACE_ID = config('AFFINDA_WORKSPACE_ID', default='')
AFFINDA_COLLECTION_ID = config('AFFINDA_COLLECTION_ID', default='')

# OpenAI Configuration (AI tools — resume scorer, builder, interview, skill gap)
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')

# Razorpay Configuration
RAZORPAY_KEY_ID = config('RAZORPAY_KEY_ID', default='')
RAZORPAY_KEY_SECRET = config('RAZORPAY_KEY_SECRET', default='')

# Platform Revenue Split
PLATFORM_COMMISSION_PERCENTAGE = 30
EARNER_PERCENTAGE = 70

# Session and Booking Settings
SESSION_BOOKING_ADVANCE_HOURS = 24
SESSION_CANCELLATION_HOURS = 12

# File Upload Settings
MAX_UPLOAD_SIZE = 5242880  # 5MB in bytes
ALLOWED_RESUME_EXTENSIONS = ['pdf', 'doc', 'docx']
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif']
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880   # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880   # 5MB

# Security — cookie settings
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# Logging — console only by default; prod.py overrides fully
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'admin_access': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
