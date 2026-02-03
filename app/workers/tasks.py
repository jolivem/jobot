from sqlalchemy.orm import Session
from app.workers.celery_app import celery
from app.core.db import SessionLocal
from app.repositories.alert_repo import AlertRepository
from app.services.binance_price_service import BinancePriceService

@celery.task(name="app.workers.tasks.check_price_alerts")
def check_price_alerts():
    db: Session = SessionLocal()
    try:
        repo = AlertRepository(db)
        binance = BinancePriceService()

        alerts = repo.list_active()
        for a in alerts:
            try:
                price = binance.get_price(a.symbol)
            except Exception:
                continue

            hit = (price >= a.target_price) if a.direction == "above" else (price <= a.target_price)
            if hit:
                repo.mark_triggered(a, price)

    finally:
        db.close()
