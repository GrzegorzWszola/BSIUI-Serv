"""Key management routes for X3DH key bundles and one-time prekeys.

New router — no equivalent existed in the original Python backend.
Mirrors ``BSIUI-serv-BUN/src/modules/keys/``.

Endpoints:
- ``GET  /{username}/keys``  — fetch another user's public bundle (consumes
  one OPK).
- ``GET  /keys/opk``         — count the caller's remaining one-time prekeys.
- ``POST /keys/opk``         — upload fresh one-time prekeys.
"""

from fastapi import APIRouter, HTTPException
from sqlmodel import asc, func, select

from app.crypto import assert_public_keys
from app.database import SessionDep
from app.models import (
    KeyBundleRead,
    MAX_ONE_TIME_PREKEYS,
    OneTimePrekey,
    OpkCount,
    OpkUpload,
    User,
    UserKey,
)
from app.security import CurrentUser

router = APIRouter(tags=["keys"])


@router.get(
    "/{username}/keys",
    response_model=KeyBundleRead,
)
def get_key_bundle(
    username: str, session: SessionDep, current_user: CurrentUser
):
    """Fetch another user's public X3DH bundle.

    The oldest one-time prekey is consumed (deleted) and returned as
    ``opk_pub``.  If the user has no remaining OPKs, ``opk_pub`` is ``null``
    and the client should fall back to 3-DH.
    """
    user = session.exec(
        select(User).where(User.username == username)
    ).first()
    if not user:
        raise HTTPException(
            status_code=404, detail="Taki użytkownik nie istnieje"
        )
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Nie możesz pobrać własnych kluczy",
        )

    keys = session.exec(
        select(UserKey).where(UserKey.user_id == user.id)
    ).first()
    if not keys:
        raise HTTPException(
            status_code=404, detail="Użytkownik nie ma kluczy"
        )

    # Consume the oldest one-time prekey (if any).
    oldest_opk = session.exec(
        select(OneTimePrekey)
        .where(OneTimePrekey.user_id == user.id)
        .order_by(asc(OneTimePrekey.id))
        .limit(1)
    ).first()

    opk_pub_value: str | None = None
    if oldest_opk:
        opk_pub_value = oldest_opk.opk_pub
        session.delete(oldest_opk)
        session.commit()

    return KeyBundleRead(
        username=username,
        ik_pub=keys.ik_pub,
        spk_pub=keys.spk_pub,
        sig=keys.sig,
        opk_pub=opk_pub_value,
    )


@router.get("/keys/opk", response_model=OpkCount)
def get_opk_count(session: SessionDep, current_user: CurrentUser):
    """Return the number of the caller's one-time prekeys still on the server."""
    count = session.exec(
        select(func.count(OneTimePrekey.id)).where(
            OneTimePrekey.user_id == current_user.id
        )
    ).one()
    return OpkCount(count=count)


@router.post("/keys/opk", response_model=OpkCount)
def upload_opks(
    data: OpkUpload, session: SessionDep, current_user: CurrentUser
):
    """Upload fresh one-time prekeys once the pool runs low.

    Duplicates are silently ignored.  The total pool size must not exceed
    ``MAX_ONE_TIME_PREKEYS``.
    """
    # Validate all keys are proper P-256 SPKI.
    assert_public_keys(data.opk_pub)

    current_count = session.exec(
        select(func.count(OneTimePrekey.id)).where(
            OneTimePrekey.user_id == current_user.id
        )
    ).one()

    if current_count + len(data.opk_pub) > MAX_ONE_TIME_PREKEYS:
        raise HTTPException(
            status_code=400, detail="Za dużo kluczy jednorazowych"
        )

    # Insert with deduplication.
    existing_keys = set(
        session.exec(
            select(OneTimePrekey.opk_pub).where(
                OneTimePrekey.user_id == current_user.id
            )
        ).all()
    )

    for opk in data.opk_pub:
        if opk not in existing_keys:
            session.add(
                OneTimePrekey(user_id=current_user.id, opk_pub=opk)
            )

    session.commit()

    new_count = session.exec(
        select(func.count(OneTimePrekey.id)).where(
            OneTimePrekey.user_id == current_user.id
        )
    ).one()
    return OpkCount(count=new_count)
