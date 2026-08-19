"""Celery task entrypoints (imported by the worker)."""

from .celery_app import run_job_task

__all__ = ["run_job_task"]


def enqueue_job(job_id: str) -> None:
    """Enqueue a job to the Celery queue (production path).

    Called by the API after creating a job row when REDIS_URL is set.
    """
    run_job_task.delay(job_id)
