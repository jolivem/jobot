from celery import Celery
from celery.signals import worker_ready
from app.core.config import settings

celery = Celery(
    "jobot_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks", "app.workers.screening_tasks", "app.workers.lstm_tasks"],
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
    "update-lstm-models-daily": {
        "task": "app.workers.lstm_tasks.update_lstm_models",
        "schedule": 86400.0,  # once per day
        "options": {"queue": "short"},
    },
}

celery.conf.task_routes = {
    "app.workers.tasks.cache_prices": {"queue": "short"},
    "app.workers.tasks.restart_active_bots": {"queue": "short"},
    "app.workers.tasks.snapshot_pnl": {"queue": "short"},
    "app.workers.tasks.run_trading_bot": {"queue": "bots"},
    "app.workers.lstm_tasks.run_lstm_bot": {"queue": "bots"},
    "app.workers.lstm_tasks.update_lstm_models": {"queue": "short"},
    "app.workers.lstm_tasks.restart_active_lstm_bots": {"queue": "short"},
}


@worker_ready.connect
def on_worker_ready(**kwargs):
    """When the worker starts, restart all active trading bots."""
    celery.send_task("app.workers.tasks.restart_active_bots")
    celery.send_task("app.workers.lstm_tasks.restart_active_lstm_bots")
