from datetime import timedelta
from secrets import compare_digest, token_urlsafe

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.time import utc_now

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expire = utc_now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> int | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        subject = payload.get("sub")
        return int(subject) if subject else None
    except (JWTError, TypeError, ValueError):
        return None


def generate_csrf_token() -> str:
    return token_urlsafe(32)


def verify_csrf_token(cookie_token: str | None, form_token: str | None) -> bool:
    if not cookie_token or not form_token:
        return False
    return compare_digest(cookie_token, form_token)
