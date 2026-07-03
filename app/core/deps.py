from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.channel import Channel
from app.models.client import Client
from app.models.conversation import Conversation
from app.models.user import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    user_id = decode_access_token(token)
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active or not user.workspace or not user.workspace.is_active:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas administradores.")
    return current_user


def get_workspace_conversation(db: Session, current_user: User, conversation_id: int) -> Conversation | None:
    return (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.workspace_id == current_user.workspace_id)
        .first()
    )


def get_workspace_user(db: Session, current_user: User, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id, User.workspace_id == current_user.workspace_id).first()


def get_workspace_channel(db: Session, current_user: User, channel_id: int) -> Channel | None:
    return db.query(Channel).filter(Channel.id == channel_id, Channel.workspace_id == current_user.workspace_id).first()


def get_workspace_client(db: Session, current_user: User, client_id: int) -> Client | None:
    return db.query(Client).filter(Client.id == client_id, Client.workspace_id == current_user.workspace_id).first()
