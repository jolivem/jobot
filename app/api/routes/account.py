import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.encryption import decrypt
from app.api.deps import get_current_user
from app.services.binance_trade_service import BinanceTradeService

router = APIRouter(prefix="/account", tags=["account"])


def _get_binance_keys(user):
    if not user.binance_api_key or not user.binance_api_secret:
        raise HTTPException(status_code=400, detail="Binance API keys not configured")
    try:
        api_key = decrypt(user.binance_api_key)
        api_secret = decrypt(user.binance_api_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to decrypt API keys")
    return api_key, api_secret


@router.get("/bnb-balance")
def bnb_balance(user=Depends(get_current_user)):
    """Return the user's free BNB balance on Binance."""
    api_key, api_secret = _get_binance_keys(user)
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
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Connection error: {str(e)}")

    balances = r.json().get("balances", [])
    for b in balances:
        if b["asset"] == "BNB":
            return {"free": float(b["free"]), "locked": float(b["locked"])}

    return {"free": 0.0, "locked": 0.0}


class ConvertToBnbRequest(BaseModel):
    amount: float = Field(gt=0, description="USDC amount to convert to BNB")


@router.post("/convert-to-bnb")
def convert_to_bnb(payload: ConvertToBnbRequest, user=Depends(get_current_user)):
    """Buy BNB with USDC via a market order on the BNBUSDC pair."""
    api_key, api_secret = _get_binance_keys(user)
    binance = BinanceTradeService(api_key, api_secret)

    # Get current BNB price in USDC to compute quantity
    try:
        r = binance.client.get(
            f"{binance.base_url}/api/v3/ticker/price",
            params={"symbol": "BNBUSDC"},
        )
        r.raise_for_status()
        bnb_price = float(r.json()["price"])
    except Exception:
        raise HTTPException(status_code=503, detail="Could not fetch BNB price")

    quantity = payload.amount / bnb_price

    try:
        result = binance.place_order("BNBUSDC", "BUY", quantity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Order failed: {str(e)}")

    fills = result.get("fills", [])
    total_qty = sum(float(f["qty"]) for f in fills)
    total_cost = sum(float(f["qty"]) * float(f["price"]) for f in fills)

    return {
        "status": result.get("status"),
        "bnb_bought": total_qty,
        "usdc_spent": total_cost,
    }
