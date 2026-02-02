from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.repositories.user_repo import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("not access token")
        user_id = int(payload["sub"])
        user = UserRepository(db).get_by_id(user_id)
        if not user:
            raise ValueError("user not found")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_admin(user = Depends(get_current_user)):
    if getattr(user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user
