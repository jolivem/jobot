import json
import time
from fastapi import APIRouter
from sqlalchemy import text
from app.core.cache import RedisCache
from app.core.db import SessionLocal
from app.workers.celery_app import celery

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health():
    return {
        "status": "ok",
        "redis": _check_redis(),
        "database": _check_database(),
        "celery": _check_celery(),
        "price_feed": _check_price_feed(),
    }


def _check_redis() -> dict:
    try:
        cache = RedisCache()
        if not cache.client.ping():
            return {"connected": False}
        info = cache.client.info(section="memory")
        clients = cache.client.info(section="clients")
        price_keys = cache.client.keys("price:*")
        bot_loop_running = cache.client.exists("bot_loop_lock")
        tick_ms_raw = cache.client.get("bot_loop_tick_ms")
        tick_ms = int(tick_ms_raw) if tick_ms_raw else None
        return {
            "connected": True,
            "used_memory_human": info.get("used_memory_human", "?"),
            "connected_clients": clients.get("connected_clients", 0),
            "cached_prices": len(price_keys),
            "bot_loop_running": bool(bot_loop_running),
            "bot_loop_tick_ms": tick_ms,
        }
    except Exception:
        return {"connected": False}


def _check_database() -> dict:
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return {"connected": True}
        finally:
            db.close()
    except Exception as e:
        return {"connected": False, "error": str(e)}


def _check_celery() -> dict:
    result = {"workers": []}
    try:
        inspector = celery.control.inspect(timeout=2.0)
        ping = inspector.ping() or {}
        active = inspector.active() or {}
        stats = inspector.stats() or {}
        for worker_name, _ in ping.items():
            worker_stats = stats.get(worker_name, {})
            active_tasks = active.get(worker_name, [])
            pool = worker_stats.get("pool", {})
            result["workers"].append({
                "name": worker_name,
                "status": "online",
                "active_tasks": len(active_tasks),
                "concurrency": pool.get("max-concurrency", "?"),
                "processed": worker_stats.get("total", {}).keys().__len__() if isinstance(worker_stats.get("total"), dict) else 0,
            })
    except Exception:
        pass
    result["online"] = len(result["workers"])
    return result


def _check_price_feed() -> dict:
    """Check if prices are fresh (updated within last 10 seconds)."""
    try:
        cache = RedisCache()
        price_keys = cache.client.keys("price:*")
        if not price_keys:
            return {"status": "no_data", "fresh_prices": 0, "stale_prices": 0}
        now = time.time()
        fresh = 0
        stale = 0
        stale_symbols = []
        for key in price_keys:
            data = cache.client.get(key)
            if data:
                ts = json.loads(data).get("timestamp", 0)
                if now - ts < 10:
                    fresh += 1
                else:
                    stale += 1
                    stale_symbols.append(key.replace("price:", ""))
        status = "ok" if stale == 0 and fresh > 0 else "degraded" if fresh > 0 else "down"
        result = {"status": status, "fresh_prices": fresh, "stale_prices": stale}
        if stale_symbols:
            result["stale_symbols"] = stale_symbols[:10]
        return result
    except Exception:
        return {"status": "error"}
