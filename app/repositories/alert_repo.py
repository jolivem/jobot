from sqlalchemy.orm import Session
from app.models.alert import PriceAlert
from app.models.alert_event import AlertEvent

class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: int, symbol: str, target_price: float, direction: str) -> PriceAlert:
        row = PriceAlert(
            user_id=user_id,
            symbol=symbol.upper().strip(),
            target_price=target_price,
            direction=direction,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_by_user(self, user_id: int) -> list[PriceAlert]:
        return self.db.query(PriceAlert).filter(PriceAlert.user_id == user_id).order_by(PriceAlert.id.desc()).all()

    def get_by_id(self, user_id: int, alert_id: int) -> PriceAlert | None:
        return self.db.query(PriceAlert).filter(PriceAlert.user_id == user_id, PriceAlert.id == alert_id).first()

    def deactivate(self, user_id: int, alert_id: int) -> PriceAlert | None:
        row = self.get_by_id(user_id, alert_id)
        if not row:
            return None
        row.is_active = 0
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, user_id: int, alert_id: int) -> bool:
        row = self.get_by_id(user_id, alert_id)
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    # Worker usage
    def list_active(self) -> list[PriceAlert]:
        return self.db.query(PriceAlert).filter(PriceAlert.is_active == 1).all()

    def mark_triggered(self, alert: PriceAlert, triggered_price: float) -> AlertEvent:
        alert.is_active = 0
        ev = AlertEvent(
            alert_id=alert.id,
            user_id=alert.user_id,
            symbol=alert.symbol,
            triggered_price=triggered_price,
        )
        self.db.add(ev)
        self.db.commit()
        self.db.refresh(ev)
        return ev

    def list_events_by_user(self, user_id: int) -> list[AlertEvent]:
        return self.db.query(AlertEvent).filter(AlertEvent.user_id == user_id).order_by(AlertEvent.id.desc()).all()
