from datetime import datetime, timezone

from pydantic import Field as PydanticField
from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlmodel import Field, SQLModel

MAX_ONE_TIME_PREKEYS = 100

# ---------------------------------------------------------------------------
# Database tables
# ---------------------------------------------------------------------------


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str


class UserKey(SQLModel, table=True):
    """Public half of a user's X3DH key bundle.

    Private keys never reach the server.
    """

    __tablename__ = "user_key"

    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    ik_pub: str
    spk_pub: str
    sig: str


class OneTimePrekey(SQLModel, table=True):
    """Pool of one-time prekeys; each row is handed out once and deleted."""

    __tablename__ = "one_time_prekey"
    __table_args__ = (UniqueConstraint("user_id", "opk_pub"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    opk_pub: str


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sender_id: int = Field(foreign_key="user.id", index=True)
    receiver_id: int = Field(foreign_key="user.id", index=True)
    msg: str
    # E2EE metadata — nullable only for messages created before E2EE was added.
    iv: str | None = None
    ek_pub: str | None = None
    opk_pub: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )


# ---------------------------------------------------------------------------
# Pydantic schemas (request / response bodies — no table)
# ---------------------------------------------------------------------------


class UserCreate(SQLModel):
    """Registration payload: credentials + full X3DH key bundle."""

    login: str
    password: str
    ik_pub: str
    spk_pub: str
    sig: str
    opk_pub: list[str] = PydanticField(max_length=MAX_ONE_TIME_PREKEYS)


class UserRead(SQLModel):
    id: int
    username: str


class MessageCreate(SQLModel):
    """Send-message payload: ciphertext + IV (keys travel in headers)."""

    receiver_name: str
    msg: str
    iv: str


class MessageRead(SQLModel):
    id: int
    sender_name: str
    receiver_name: str
    msg: str
    iv: str | None = None
    ek_pub: str | None = None
    opk_pub: str | None = None
    created_at: datetime


class KeyBundleRead(SQLModel):
    """Public key bundle returned when initiating X3DH with another user."""

    username: str
    ik_pub: str
    spk_pub: str
    sig: str
    opk_pub: str | None = None


class OpkUpload(SQLModel):
    """Body for uploading fresh one-time prekeys."""

    opk_pub: list[str] = PydanticField(
        min_length=1, max_length=MAX_ONE_TIME_PREKEYS
    )


class OpkCount(SQLModel):
    count: int
