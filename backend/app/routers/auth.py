from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.schemas import AuthResponse, DemoAuthRequest, GoogleAuthRequest, UserOut
from app.security import (
    create_access_token,
    get_current_user,
    get_or_create_demo_user,
    get_or_create_user,
    verify_google_id_token,
)
from app.models import User

settings = get_settings()

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/google", response_model=AuthResponse)
def google_sign_in(body: GoogleAuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    claims = verify_google_id_token(body.id_token)
    user = get_or_create_user(db, claims)
    token = create_access_token(user)
    return AuthResponse(token=token, user=UserOut.model_validate(user))


@router.post("/demo", response_model=AuthResponse)
def demo_sign_in(body: DemoAuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    if not settings.allow_demo_login:
        raise HTTPException(status_code=404, detail="Demo login is disabled")
    user = get_or_create_demo_user(db, body.demo_id)
    token = create_access_token(user)
    return AuthResponse(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
