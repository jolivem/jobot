from pydantic import BaseModel, EmailStr, Field


def _mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    binance_api_key: str | None = None
    binance_api_secret: str | None = None

    @classmethod
    def from_user(cls, user) -> "MeResponse":
        return cls(
            id=user.id,
            email=user.email,
            role=user.role,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            binance_api_key=_mask_secret(user.binance_api_key),
            binance_api_secret=_mask_secret(user.binance_api_secret),
        )


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=100)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    binance_api_key: str | None = Field(default=None, max_length=255)
    binance_api_secret: str | None = Field(default=None, max_length=255)
