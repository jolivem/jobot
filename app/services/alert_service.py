from sqlalchemy.orm import Session
from app.repositories.alert_repo import AlertRepository

class AlertService:
    def __init__(self, db: Session):
        self.repo = AlertRepository(db)

    def _validate_direction(self, direction: str) -> str:
        d = direction.lower().strip()
        if d not in ("above", "below"):
            raise ValueError("direction must be 'above' or 'below'")
        return d

    def create(self, user_id: int, symbol: str, target_price: float, direction: str):
        d = self._validate_direction(direction)
        return self.repo.create(user_id=user_id, symbol=symbol, target_price=target_price, direction=d)

    def list(self, user_id: int):
        return self.repo.list_by_user(user_id)

    def deactivate(self, user_id: int, alert_id: int):
        return self.repo.deactivate(user_id, alert_id)

    def delete(self, user_id: int, alert_id: int) -> bool:
        return self.repo.delete(user_id, alert_id)

    def events(self, user_id: int):
        return self.repo.list_events_by_user(user_id)
