from sqlalchemy.orm import Session
from app.repositories.portfolio_repo import PortfolioRepository
from app.services.binance_price_service import BinancePriceService

class PortfolioService:
    def __init__(self, db: Session, price_service: BinancePriceService | None = None):
        self.repo = PortfolioRepository(db)
        self.prices = price_service or BinancePriceService()

    def list_assets(self, user_id: int):
        return self.repo.list_by_user(user_id)

    def upsert_asset(self, user_id: int, symbol: str, quantity: float):
        return self.repo.upsert(user_id=user_id, symbol=symbol, quantity=quantity)

    def delete_asset(self, user_id: int, asset_id: int) -> bool:
        return self.repo.delete(user_id=user_id, asset_id=asset_id)

    def get_valuation(self, user_id: int) -> dict:
        assets = self.repo.list_by_user(user_id)
        total = 0.0
        items = []
        for a in assets:
            price = self.prices.get_price(a.symbol)
            value = price * a.quantity
            total += value
            items.append({
                "symbol": a.symbol,
                "quantity": a.quantity,
                "price": price,
                "value": value,
            })
        return {"total_value": total, "items": items}
