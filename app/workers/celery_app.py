from celery import Celery
from app.core.config import settings

celery = Celery(
    "jobot_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

# Note: Price caching is handled by WebSocket worker (websocket_worker.py)
# Trading bot tasks are launched on-demand (one long-running task per active bot)
celery.conf.beat_schedule = {}
