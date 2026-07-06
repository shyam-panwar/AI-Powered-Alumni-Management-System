from decouple import config

settings_module = config('DJANGO_SETTINGS_MODULE', default='')
environment = config('ENVIRONMENT', default='dev')

if settings_module.endswith('.prod') or environment == 'prod':
    from .prod import *
else:
    from .dev import *
