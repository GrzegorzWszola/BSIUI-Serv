"""Auth routes: registration (with X3DH key bundle) and login.

Changes vs. the original:
- Registration now accepts and validates a full X3DH key bundle.
- User + keys are stored in a single transaction (race-condition safe).
- Key bundle is cryptographically validated (P-256 format + SPK signature).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app.crypto import validate_bundle
from app.database import SessionDep
from app.models import OneTimePrekey, User, UserCreate, UserKey, UserRead
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
def register(data: UserCreate, session: SessionDep):
    # Quick pre-check (outside transaction) to fail fast on duplicates.
    if session.exec(select(User).where(User.username == data.login)).first():
        raise HTTPException(status_code=400, detail="Użytkownik już istnieje")

    # Validate the key bundle *before* touching the DB — this can be expensive.
    validate_bundle(data.ik_pub, data.spk_pub, data.sig, data.opk_pub)

    # --- atomic transaction: create user + store keys ---
    # Re-check inside the transaction to prevent TOCTOU races.
    if session.exec(select(User).where(User.username == data.login)).first():
        raise HTTPException(status_code=400, detail="Użytkownik już istnieje")

    user = User(
        username=data.login,
        hashed_password=hash_password(data.password),
    )
    session.add(user)
    session.flush()  # assigns user.id without committing

    # Store the public key bundle.
    user_key = UserKey(
        user_id=user.id,
        ik_pub=data.ik_pub,
        spk_pub=data.spk_pub,
        sig=data.sig,
    )
    session.add(user_key)

    # Store one-time prekeys.
    for opk in data.opk_pub:
        session.add(OneTimePrekey(user_id=user.id, opk_pub=opk))

    session.commit()
    session.refresh(user)
    return user


@router.post("/login")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
):
    user = session.exec(
        select(User).where(User.username == form.username)
    ).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Zły login lub hasło")
    return {
        "access_token": create_access_token(user.username),
        "token_type": "bearer",
    }
