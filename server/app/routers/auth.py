"""Authentication endpoints: signup, login, refresh, me."""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.app.core.config import get_settings
from server.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    validate_password_policy,
)
from server.app.core.deps import get_current_user
from server.app.db.auth_db import get_auth_session
from server.app.db.ops_db import get_ops_session
from server.app.db.models_auth import User, FleetDriver
from server.app.db.sync import ensure_user_thresholds
from server.app.schemas.auth import (
    UserSignupRequest,
    UserLoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: UserSignupRequest,
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """Register a new driver or fleet manager."""
    # Validate password complexity
    valid_pw, reason = validate_password_policy(payload.password)
    if not valid_pw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

    # Check email uniqueness
    existing = auth_db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Create user
    pw_hash = hash_password(payload.password)
    user = User(
        full_name=payload.full_name,
        email=payload.email.lower(),
        password_hash=pw_hash,
        role=payload.role,
        is_active=True,
    )
    auth_db.add(user)
    auth_db.commit()
    auth_db.refresh(user)

    # If driver, provision default threshold in ops_db
    if user.role == "driver":
        ensure_user_thresholds(ops_db, user.id)

    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        fleet_id=None,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLoginRequest,
    auth_db: Session = Depends(get_auth_session),
):
    """Authenticate and obtain JWT access + refresh tokens."""
    user = auth_db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive.",
        )

    access_token = create_access_token(user_id=user.id, role=user.role)
    refresh_token = create_refresh_token(user_id=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    payload: TokenRefreshRequest,
    auth_db: Session = Depends(get_auth_session),
):
    """Exchange a valid refresh token for a new access token."""
    try:
        data = decode_token(payload.refresh_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    if data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is not a refresh token.")

    user_id = data.get("sub")
    user = auth_db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive.")

    new_access = create_access_token(user_id=user.id, role=user.role)
    new_refresh = create_refresh_token(user_id=user.id)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    auth_db: Session = Depends(get_auth_session),
):
    """Retrieve details of the currently authenticated user."""
    fd = auth_db.query(FleetDriver).filter(FleetDriver.driver_id == current_user.id).first()
    fleet_id = fd.fleet_id if fd else None

    return UserResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        fleet_id=fleet_id,
    )
