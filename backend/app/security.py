import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.utils.naming import user_schema_name

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

JWT_ALGORITHM = "HS256"


def verify_google_id_token(raw_id_token: str) -> dict:
    """Verify a Google Identity Services ID token and return its claims.

    Raises HTTPException(401) if the token is invalid, expired, or was not
    issued for our configured OAuth client.
    """
    try:
        claims = google_id_token.verify_oauth2_token(
            raw_id_token, google_requests.Request(), settings.google_client_id
        )
    except Exception as exc:  # noqa: BLE001 - library raises broad ValueError
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {exc}") from exc

    if claims.get("aud") != settings.google_client_id:
        raise HTTPException(status_code=401, detail="Google token was not issued for this app")

    return claims


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session token") from exc


def _new_user(google_sub: str, email: str, name: str, picture: str) -> User:
    """Build a User with `id` and the derived `snowflake_schema` set together,
    so the very first INSERT already satisfies the NOT NULL constraint instead
    of relying on a flush-then-backfill that fails on the initial insert.
    """
    user_id = uuid.uuid4().hex
    return User(
        id=user_id,
        google_sub=google_sub,
        email=email,
        name=name,
        picture=picture,
        snowflake_schema=user_schema_name(user_id),
    )


DEMO_PROFILES: dict[str, str] = {
    "demo-a": "Demo User A",
    "demo-b": "Demo User B",
}


def get_or_create_demo_user(db: Session, demo_id: str) -> User:
    """Local-only stand-in for Google Sign-In, for demoing without OAuth access.

    Only ever creates one of the two fixed profiles in DEMO_PROFILES — never an
    arbitrary user — so this endpoint can't be used to mint accounts at will.
    """
    if demo_id not in DEMO_PROFILES:
        raise HTTPException(status_code=400, detail="Unknown demo account")

    google_sub = f"demo:{demo_id}"
    user = db.query(User).filter(User.google_sub == google_sub).one_or_none()
    if user:
        return user

    user = _new_user(google_sub, f"{demo_id}@demo.local", DEMO_PROFILES[demo_id], "")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_user(db: Session, claims: dict) -> User:
    google_sub = claims["sub"]
    user = db.query(User).filter(User.google_sub == google_sub).one_or_none()
    if user:
        return user

    user = _new_user(
        google_sub, claims.get("email", ""), claims.get("name", ""), claims.get("picture", "")
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = decode_access_token(credentials.credentials)
    user = db.query(User).filter(User.id == payload["sub"]).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
