import hashlib
from base64 import b64encode
from datetime import UTC, datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _prehash(password: str) -> str:
    """SHA-256 pre-hash so bcrypt never receives >72 bytes."""
    return b64encode(hashlib.sha256(password.encode("utf-8")).digest()).decode("ascii")


class TokenService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(_prehash(plain_password), hashed_password)

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(_prehash(password))

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
