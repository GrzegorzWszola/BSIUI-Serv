from fastapi import APIRouter, HTTPException
from sqlmodel import func, or_, select

from app.database import SessionDep
from app.models import Message, MessageCreate, MessageRead, User
from app.security import CurrentUser

router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("", status_code=201)
def send_message(data: MessageCreate, session: SessionDep, current_user: CurrentUser):
    if not data.msg.strip():
        raise HTTPException(status_code=400, detail="Pusta wiadomość")

    receiver_id = session.exec(
        select(User.id).where(User.username == data.receiver_name)
    ).first()
    if receiver_id is None:
        raise HTTPException(status_code=404, detail="Odbiorca nie istnieje")

    if receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Nie możesz pisać do siebie")

    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        msg=data.msg,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return {"id": message.id, "created_at": message.created_at}

@router.get("/update/{since_id}", status_code=200)
def update_messages(since_id: int, session: SessionDep, current_user: CurrentUser):
    statement = (
        select(User.username, func.count(Message.id), func.max(Message.id))
        .join(User, User.id == Message.sender_id)
        .where(Message.receiver_id == current_user.id, Message.id > since_id)
        .group_by(User.username)
    )
    rows = session.exec(statement).all()

    return {
        "senders": [
            {"username": u, "count": c, "last_id": last} for u, c, last in rows
        ]
    }

@router.get("/history/{since_id}/{receiver_name}", response_model=list[MessageRead])
def get_message_history(
    since_id: int, 
    receiver_name: str, 
    session: SessionDep, 
    current_user: CurrentUser
):
    receiver = session.exec(select(User).where(User.username == receiver_name)).first()

    if not receiver:
        raise HTTPException(status_code=404, detail="Taki użytkownik nie istnieje")

    statement = select(Message).where(
        Message.id > since_id,
        or_(
            (Message.sender_id == current_user.id) & (Message.receiver_id == receiver.id),
            (Message.sender_id == receiver.id) & (Message.receiver_id == current_user.id)
        )
    ).order_by(Message.id.asc())

    messages = session.exec(statement).all()
    names = {current_user.id: current_user.username, receiver.id: receiver.username}
    return [
        MessageRead(
            id=m.id,
            sender_name=names[m.sender_id],
            receiver_name=names[m.receiver_id],
            msg=m.msg,
            created_at=m.created_at,
        )
        for m in messages
    ]