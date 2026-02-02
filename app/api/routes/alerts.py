from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.api.deps import get_current_user
from app.schemas.alert import AlertCreate, AlertRead, AlertEventRead
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.post("", response_model=AlertRead)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db), user = Depends(get_current_user)):
    try:
        return AlertService(db).create(user.id, payload.symbol, payload.target_price, payload.direction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=list[AlertRead])
def list_alerts(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return AlertService(db).list(user.id)

@router.post("/{alert_id}/deactivate", response_model=AlertRead)
def deactivate(alert_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    row = AlertService(db).deactivate(user.id, alert_id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    return row

@router.delete("/{alert_id}")
def delete(alert_id: int, db: Session = Depends(get_db), user = Depends(get_current_user)):
    ok = AlertService(db).delete(user.id, alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"deleted": True}

@router.get("/events", response_model=list[AlertEventRead])
def events(db: Session = Depends(get_db), user = Depends(get_current_user)):
    return AlertService(db).events(user.id)
