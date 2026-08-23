from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "raqib_agent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Cairo",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    worker_max_tasks_per_child=50,
)

# Explicitly import tasks so Celery registers them at startup
import app.tasks.crawl_tasks  # noqa: F401, E402
import app.tasks.notification_tasks  # noqa: F401, E402
