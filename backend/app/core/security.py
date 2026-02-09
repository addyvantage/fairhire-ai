import hashlib
from base64 import b64encode
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import jwt

from app.core.config import get_settings


def _prehash(password: str) -> bytes:
    """SHA-256 pre-hash so bcrypt never receives >72 bytes.

    Returns the base64-encoded digest as bytes, ready for bcrypt.
    """
    return b64encode(hashlib.sha256(password.encode("utf-8")).digest())


class TokenService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(_prehash(plain_password), hashed_password.encode("utf-8"))

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
        settings = get_settings()
        expire = datetime.now(UTC) + (
            expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
        )
        payload = {"sub": subject, "exp": expire}
        return jwt.encode(payload, settings.secret_key, algorithm="HS256")


# Convenience aliases used by app.api.routes.auth
get_password_hash = TokenService.hash_password
verify_password = TokenService.verify_password
create_access_token = TokenService.create_access_token
