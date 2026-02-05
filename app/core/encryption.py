from cryptography.fernet import Fernet
from app.core.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return the ciphertext as a URL-safe base64 string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a URL-safe base64 ciphertext string back to plaintext."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
