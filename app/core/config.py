from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "dev"
    APP_NAME: str = "Jobot API"
    LOG_LEVEL: str = "INFO"

    JWT_SECRET: str
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 14

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "jobot"
    DB_PASSWORD: str = "jobot_password"
    DB_NAME: str = "jobot_db"

    REDIS_URL: str = "redis://localhost:6379/0"
    BINANCE_BASE_URL: str = "https://api.binance.com"

    # Optional override for tests
    DB_URL_OVERRIDE: str | None = None

    @property
    def db_url(self) -> str:
        if self.DB_URL_OVERRIDE:
            return self.DB_URL_OVERRIDE
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

settings = Settings()
