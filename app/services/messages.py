from datetime import datetime

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import Message


def create_message(db: Session, conversation: Conversation, sender: str, text: str, is_internal: bool = False, scheduled_for: datetime | None = None) -> Message:
    now = datetime.utcnow()
    is_future_schedule = scheduled_for and scheduled_for > now
    status = "agendada" if is_future_schedule else "enviada"
    message = Message(
        conversation_id=conversation.id,
        sender=sender,
        text=text,
        is_internal=is_internal,
        scheduled_for=scheduled_for,
        status=status,
    )
    if not is_internal and not is_future_schedule:
        conversation.last_message_at = now
        if sender == "atendente":
            conversation.unread = False
            if conversation.first_response_at is None:
                conversation.first_response_at = now
                conversation.first_response_minutes = int((now - conversation.created_at).total_seconds() // 60)
        elif sender == "cliente":
            conversation.unread = True
    db.add(message)
    db.add(conversation)
    db.commit()
    db.refresh(message)
    return message


def process_scheduled_messages(db: Session) -> int:
    now = datetime.utcnow()
    messages = db.query(Message).filter(Message.status == "agendada", Message.scheduled_for <= now).all()
    for message in messages:
        message.status = "enviada"
        message.created_at = now
        conversation = message.conversation
        conversation.last_message_at = now
        if message.sender == "atendente" and conversation.first_response_at is None:
            conversation.first_response_at = now
            conversation.first_response_minutes = int((now - conversation.created_at).total_seconds() // 60)
    db.commit()
    return len(messages)
