from celery import Celery
from app.core.config import settings

celery = Celery(
    "jobot_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

# Check price alerts every 30 seconds
celery.conf.beat_schedule = {
    "check-price-alerts-every-30s": {
        "task": "app.workers.tasks.check_price_alerts",
        "schedule": 30.0,
    }
}
