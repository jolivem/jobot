import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.db import get_db
from app.core.config import settings
from app.core.encryption import decrypt
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest,
    MeResponse, LogoutRequest, UserUpdate,
)
from app.services.auth_service import AuthService
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=MeResponse)
@limiter.limit("10/hour")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = AuthService(db).register(payload.email, payload.password, role="user")
        return MeResponse.from_user(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/verify/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        AuthService(db).verify_email(token)
        return {"verified": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        return AuthService(db).login(payload.email, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        return AuthService(db).refresh(payload.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout", status_code=204)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    try:
        AuthService(db).logout(payload.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=MeResponse)
def me(user=Depends(get_current_user)):
    return MeResponse.from_user(user)


@router.patch("/me", response_model=MeResponse)
def update_me(payload: UserUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        updated = AuthService(db).update_profile(user.id, **data)
        return MeResponse.from_user(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/me/verify-binance")
@limiter.limit("5/minute")
def verify_binance_keys(request: Request, user=Depends(get_current_user)):
    if not user.binance_api_key or not user.binance_api_secret:
        raise HTTPException(status_code=400, detail="Binance API keys not configured")

    try:
        api_key = decrypt(user.binance_api_key)
        api_secret = decrypt(user.binance_api_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to decrypt API keys")

    base_url = settings.BINANCE_BASE_URL.rstrip("/")
    params = {"timestamp": int(time.time() * 1000)}
    query = urlencode(params)
    signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = signature

    try:
        r = httpx.get(
            f"{base_url}/api/v3/account",
            params=params,
            headers={"X-MBX-APIKEY": api_key},
            timeout=10.0,
        )
        if r.status_code != 200:
            error_msg = r.json().get("msg", "Unknown error from Binance")
            raise HTTPException(status_code=400, detail=f"Binance API error: {error_msg}")
        return {"valid": True}
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Connection error: {str(e)}")
