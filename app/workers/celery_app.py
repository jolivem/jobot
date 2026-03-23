from celery import Celery
from celery.signals import worker_ready
from app.core.config import settings

celery = Celery(
    "jobot_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks", "app.workers.screening_tasks"],
)

celery.conf.beat_schedule_filename = "/tmp/celerybeat-schedule"
celery.conf.beat_schedule = {
    "cache-prices-every-3s": {
        "task": "app.workers.tasks.cache_prices",
        "schedule": 3.0,
        "options": {"queue": "short"},
    },
    "snapshot-pnl-every-hour": {
        "task": "app.workers.tasks.snapshot_pnl",
        "schedule": 3600.0,
        "options": {"queue": "short"},
    },
}

celery.conf.task_routes = {
    "app.workers.tasks.cache_prices": {"queue": "short"},
    "app.workers.tasks.restart_active_bots": {"queue": "short"},
    "app.workers.tasks.snapshot_pnl": {"queue": "short"},
    "app.workers.tasks.run_trading_bot": {"queue": "bots"},
}


@worker_ready.connect
def on_worker_ready(**kwargs):
    """When the worker starts, restart all active trading bots."""
    celery.send_task("app.workers.tasks.restart_active_bots")
