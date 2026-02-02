from sqlalchemy.orm import Session
from app.models.refresh_token import RefreshToken

class RefreshTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def store(self, user_id: int, jti: str) -> RefreshToken:
        row = RefreshToken(user_id=user_id, jti=jti)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def is_revoked(self, jti: str) -> bool:
        row = self.db.query(RefreshToken).filter(RefreshToken.jti == jti).first()
        return (row is None) or (row.is_revoked == 1)

    def revoke(self, jti: str) -> None:
        row = self.db.query(RefreshToken).filter(RefreshToken.jti == jti).first()
        if row:
            row.is_revoked = 1
            self.db.commit()
