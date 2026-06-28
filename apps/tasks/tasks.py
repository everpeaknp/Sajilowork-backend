"""Celery tasks for task lifecycle maintenance."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def update_overdue_tasks():
    """Cancel open tasks that are past their due date."""
    from apps.tasks.services import TaskService

    try:
        count = TaskService.auto_expire_old_tasks()
        logger.info('update_overdue_tasks: expired %s task(s)', count)
        return count
    except Exception:
        logger.exception('update_overdue_tasks failed')
        return 0
