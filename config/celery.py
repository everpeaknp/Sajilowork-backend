"""
Celery configuration for async task processing.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('airtasker')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    'send-pending-notifications-every-5-minutes': {
        'task': 'apps.notifications.tasks.send_pending_notifications',
        'schedule': crontab(minute='*/5'),
    },
    'cleanup-expired-tokens-daily': {
        'task': 'apps.accounts.tasks.cleanup_expired_tokens',
        'schedule': crontab(hour=2, minute=0),
    },
    'process-pending-payouts-hourly': {
        'task': 'apps.payments.tasks.process_pending_payouts',
        'schedule': crontab(minute=0),
    },
    'auto-release-escrow-hourly': {
        'task': 'apps.payments.tasks.auto_release_escrow',
        'schedule': crontab(minute=15),
    },
    'sync-payment-status-every-10-minutes': {
        'task': 'apps.payments.tasks.sync_payment_status',
        'schedule': crontab(minute='*/10'),
    },
    'update-task-statuses-every-hour': {
        'task': 'apps.tasks.tasks.update_overdue_tasks',
        'schedule': crontab(minute=30),
    },
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
