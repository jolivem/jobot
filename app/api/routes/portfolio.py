from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.api.deps import get_current_user
from app.schemas.portfolio import PortfolioUpsert, PortfolioRead
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.get("", response_model=list[PortfolioRead])
def list_assets(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return PortfolioService(db).list_assets(user.id)

@router.post("", response_model=PortfolioRead)
def upsert_asset(payload: PortfolioUpsert, db: Session = Depends(get_db), user = Depends(get_current_user)):
    return PortfolioService(db).upsert_asset(user.id, payload.symbol, payload.quantity)

@router.delete("/{asset_id}")
def delete_asset(asset_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    ok = PortfolioService(db).delete_asset(user.id, asset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"deleted": True}

@router.get("/valuation")
def valuation(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return PortfolioService(db).get_valuation(user.id)
