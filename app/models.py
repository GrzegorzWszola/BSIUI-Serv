from datetime import datetime, timezone

from sqlmodel import Field, SQLModel

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str

class UserCreate(SQLModel):
    login: str
    password: str

class UserRead(SQLModel):
    id: int
    username: str


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sender_id: int = Field(foreign_key="user.id", index=True)
    receiver_id: int = Field(foreign_key="user.id", index=True)
    msg: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )

class MessageCreate(SQLModel):
    receiver_name: str
    msg: str

class MessageRead(SQLModel):
    id: int
    sender_name: str
    receiver_name: str
    msg: str
    created_at: datetime