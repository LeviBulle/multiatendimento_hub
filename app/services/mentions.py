import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.mention_notification import MentionNotification
from app.models.message import Message
from app.models.user import User


def mention_tokens_for_user(user: User) -> set[str]:
    parts = {user.name.strip().lower(), user.email.split("@", 1)[0].lower()}
    first_name = user.name.strip().split(" ", 1)[0].lower() if user.name.strip() else ""
    if first_name:
        parts.add(first_name)
    return {part for part in parts if part}


def mentioned_users(db: Session, workspace_id: int, text: str, author_user_id: int) -> list[User]:
    normalized_text = f" {text.lower()} "
    users = (
        db.query(User)
        .filter(
            User.workspace_id == workspace_id,
            User.is_active.is_(True),
            User.id != author_user_id,
            or_(User.role == "agent", User.role == "admin"),
        )
        .all()
    )
    found = []
    for user in users:
        for token in mention_tokens_for_user(user):
            pattern = rf"(?<!\w)@{re.escape(token)}(?!\w)"
            if re.search(pattern, normalized_text):
                found.append(user)
                break
    return found


def create_mention_notifications(db: Session, conversation: Conversation, message: Message, author_user_id: int) -> list[MentionNotification]:
    if not message.is_internal or not message.text:
        return []
    notifications = []
    for user in mentioned_users(db, conversation.workspace_id, message.text, author_user_id):
        notification = MentionNotification(
            workspace_id=conversation.workspace_id,
            conversation_id=conversation.id,
            message_id=message.id,
            mentioned_user_id=user.id,
            mentioned_by_user_id=author_user_id,
        )
        db.add(notification)
        notifications.append(notification)
    db.commit()
    return notifications


def notification_context(db: Session, current_user: User) -> dict:
    query = (
        db.query(MentionNotification)
        .filter(
            MentionNotification.workspace_id == current_user.workspace_id,
            MentionNotification.mentioned_user_id == current_user.id,
            MentionNotification.is_read.is_(False),
        )
        .order_by(MentionNotification.created_at.desc())
    )
    unread = query.count()
    return {
        "mention_unread_count": unread,
        "mention_notifications": query.limit(6).all(),
    }
