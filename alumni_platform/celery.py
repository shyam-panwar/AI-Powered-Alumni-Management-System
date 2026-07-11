import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      os.getenv('DJANGO_SETTINGS_MODULE', 'alumni_platform.settings.prod'))

app = Celery('alumni_platform')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'send-session-reminders': {
        'task': 'apps.notifications.tasks.send_session_reminders',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'process-pending-payments': {
        'task': 'apps.payments.tasks.process_pending_payments',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'cleanup-expired-notifications': {
        'task': 'apps.notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'expire-old-posts': {
        'task': 'apps.feed.tasks.expire_old_posts',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
