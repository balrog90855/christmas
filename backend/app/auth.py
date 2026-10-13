import secrets
import time
from datetime import timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import config
from .models import utcnow

_bearer = HTTPBearer(auto_error=False)
_password_hash = bcrypt.hashpw(config.admin_password.encode(), bcrypt.gensalt())


def authenticate(username: str, password: str) -> bool:
    user_ok = secrets.compare_digest(username.encode(), config.admin_username.encode())
    pass_ok = bcrypt.checkpw(password.encode(), _password_hash)
    if not (user_ok and pass_ok):
        time.sleep(1)  # slow down brute forcing
        return False
    return True


def create_token() -> str:
    payload = {
        "sub": config.admin_username,
        "role": "admin",
        "exp": utcnow() + timedelta(hours=config.jwt_hours),
    }
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, config.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    if payload.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return payload["sub"]
