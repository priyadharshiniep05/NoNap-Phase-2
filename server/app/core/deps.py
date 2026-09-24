"""FastAPI dependency injection: current user extraction, role enforcement."""

from enum import Enum
from typing import Annotated

from fastapi import Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from server.app.core.security import decode_token
from server.app.db.auth_db import get_auth_session
from server.app.db.models_auth import User

from sqlalchemy.orm import Session


security_scheme = HTTPBearer()


class Role(str, Enum):
    driver = "driver"
    fleet_manager = "fleet_manager"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_auth_session),
) -> User:
    """Extract and validate the current user from the Bearer JWT token."""
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Access token required.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing user ID.")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")

    return user


def get_current_user_ws(token: str, db: Session) -> User | None:
    """Extract user from token for WebSocket auth (non-raising)."""
    try:
        payload = decode_token(token)
    except JWTError:
        return None

    if payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def require_role(required_role: Role):
    """Dependency factory that enforces a specific role on the current user."""

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role != required_role.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role.value}.",
            )
        return user

    return _check
