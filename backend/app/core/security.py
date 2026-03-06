from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from app.core.config import settings
import secrets

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=settings.JWT_EXPIRE_MINUTES
    )
    payload = {
        "sub":     user_id,
        "email":   email,
        "exp":     expire,
        "type":    "access"
    }
    return jwt.encode(payload, settings.JWT_SECRET,
                      algorithm=settings.JWT_ALGORITHM)

def create_refresh_token() -> str:
    # Refresh token = token opaque aléatoire
    # stocké en base, pas un JWT
    return secrets.token_urlsafe(64)

def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET,
                             algorithms=[settings.JWT_ALGORITHM])
        return {
            "user_id": payload.get("sub"),
            "email":   payload.get("email")
        }
    except JWTError:
        return None