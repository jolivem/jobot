from sqlalchemy.orm import Session
from app.models.portfolio import PortfolioAsset

class PortfolioRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_user(self, user_id: int) -> list[PortfolioAsset]:
        return self.db.query(PortfolioAsset).filter(PortfolioAsset.user_id == user_id).order_by(PortfolioAsset.id.desc()).all()

    def upsert(self, user_id: int, symbol: str, quantity: float) -> PortfolioAsset:
        symbol = symbol.upper().strip()
        row = self.db.query(PortfolioAsset).filter(
            PortfolioAsset.user_id == user_id,
            PortfolioAsset.symbol == symbol
        ).first()
        if row:
            row.quantity = quantity
            self.db.commit()
            self.db.refresh(row)
            return row
        row = PortfolioAsset(user_id=user_id, symbol=symbol, quantity=quantity)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, user_id: int, asset_id: int) -> bool:
        row = self.db.query(PortfolioAsset).filter(PortfolioAsset.user_id == user_id, PortfolioAsset.id == asset_id).first()
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True
