from celery import Celery
from celery.signals import worker_ready
from app.core.config import settings

celery = Celery(
    "jobot_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery.conf.beat_schedule = {
    "cache-prices-every-3s": {
        "task": "app.workers.tasks.cache_prices",
        "schedule": 3.0,
    },
}


@worker_ready.connect
def on_worker_ready(**kwargs):
    """When the worker starts, restart all active trading bots."""
    celery.send_task("app.workers.tasks.restart_active_bots")
