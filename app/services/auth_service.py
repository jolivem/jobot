import secrets
from sqlalchemy.orm import Session
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.encryption import encrypt
from app.repositories.user_repo import UserRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.refresh_repo = RefreshTokenRepository(db)

    def register(self, email: str, password: str, role: str = "user"):
        if self.users.get_by_email(email):
            raise ValueError("Email already registered")
        user = self.users.create(email=email, password_hash=hash_password(password), role=role)
        return user

    def login(self, email: str, password: str) -> dict:
        user = self.users.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")

        jti = secrets.token_hex(16)
        self.refresh_repo.store(user_id=user.id, jti=jti)

        return {
            "access_token": create_access_token(str(user.id), user.role),
            "refresh_token": create_refresh_token(str(user.id), user.role, jti),
            "token_type": "bearer",
        }

    def refresh(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")
        jti = payload.get("jti")
        if not jti or self.refresh_repo.is_revoked(jti):
            raise ValueError("Refresh token revoked")

        user_id = int(payload["sub"])
        user = self.users.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Rotate refresh token
        self.refresh_repo.revoke(jti)
        new_jti = secrets.token_hex(16)
        self.refresh_repo.store(user_id=user.id, jti=new_jti)

        return {
            "access_token": create_access_token(str(user.id), user.role),
            "refresh_token": create_refresh_token(str(user.id), user.role, new_jti),
            "token_type": "bearer",
        }

    def logout(self, refresh_token: str) -> None:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")
        jti = payload.get("jti")
        if jti:
            self.refresh_repo.revoke(jti)

    def update_profile(self, user_id: int, **data):
        # Validate email uniqueness
        if "email" in data:
            existing = self.users.get_by_email(data["email"])
            if existing and existing.id != user_id:
                raise ValueError("Email already in use")
            data["email"] = data["email"].lower()

        # Validate username uniqueness
        if "username" in data:
            existing = self.users.get_by_username(data["username"])
            if existing and existing.id != user_id:
                raise ValueError("Username already in use")

        # Hash password if provided
        if "password" in data:
            data["password_hash"] = hash_password(data.pop("password"))

        # Encrypt Binance API keys
        if "binance_api_key" in data and data["binance_api_key"]:
            data["binance_api_key"] = encrypt(data["binance_api_key"])
        if "binance_api_secret" in data and data["binance_api_secret"]:
            data["binance_api_secret"] = encrypt(data["binance_api_secret"])

        return self.users.update(user_id, **data)
