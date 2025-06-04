"""
Test settings for VIGILEOSAPP25 project.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Database - Use SQLite for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',
    }
}

# CORS settings for tests
CORS_ALLOW_ALL_ORIGINS = True

# Email backend for tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Cache - Use dummy cache for tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Test logging
LOGGING['handlers']['console']['level'] = 'DEBUG'
LOGGING['root']['level'] = 'DEBUG'
LOGGING['loggers']['django']['level'] = 'DEBUG'

# Test-specific settings
SPECTACULAR_SETTINGS.update({
    'SERVE_INCLUDE_SCHEMA': True,
})

# Disable some security features in tests
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Flag pour désactiver InfluxDB pendant les tests
TESTING = True

# InfluxDB settings for tests (use mock values)
INFLUXDB_CONFIG = {
    'url': 'http://localhost:8086',
    'token': 'test-token',
    'org': 'test-org',
    'bucket': 'test-bucket',
    'timeout': 5000,
    'verify_ssl': False,
}