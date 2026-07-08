from datetime import datetime

from sqlalchemy.orm import Session

from app.core.time import as_utc, utc_now
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.whatsapp_window_service import refresh_customer_window


def create_message(
    db: Session,
    conversation: Conversation,
    sender: str,
    text: str,
    is_internal: bool = False,
    scheduled_for: datetime | None = None,
    author_user_id: int | None = None,
    attachment_original_name: str | None = None,
    attachment_stored_name: str | None = None,
    attachment_mime_type: str | None = None,
    attachment_size_bytes: int | None = None,
    message_kind: str | None = None,
    whatsapp_template_id: int | None = None,
    status_override: str | None = None,
    failure_reason: str | None = None,
) -> Message:
    now = utc_now()
    scheduled_for = as_utc(scheduled_for)
    created_at = as_utc(conversation.created_at) or now
    is_future_schedule = scheduled_for and scheduled_for > now
    status = status_override or ("agendada" if is_future_schedule else "enviada")
    if message_kind is None:
        if is_internal:
            message_kind = "internal_note"
        elif whatsapp_template_id:
            message_kind = "template"
        elif attachment_mime_type and attachment_mime_type.startswith("audio/"):
            message_kind = "audio"
        elif attachment_original_name:
            message_kind = "attachment"
        elif sender == "sistema":
            message_kind = "system"
        else:
            message_kind = "text"
    message = Message(
        conversation_id=conversation.id,
        sender=sender,
        text=text,
        is_internal=is_internal,
        scheduled_for=scheduled_for,
        status=status,
        failure_reason=failure_reason,
        message_kind=message_kind,
        whatsapp_template_id=whatsapp_template_id,
        author_user_id=author_user_id,
        attachment_original_name=attachment_original_name,
        attachment_stored_name=attachment_stored_name,
        attachment_mime_type=attachment_mime_type,
        attachment_size_bytes=attachment_size_bytes,
    )
    if sender == "cliente":
        refresh_customer_window(conversation, now)
    if not is_internal and not is_future_schedule and status == "enviada":
        conversation.last_message_at = now
        if sender == "atendente":
            conversation.unread = False
            if conversation.first_response_at is None:
                conversation.first_response_at = now
                conversation.first_response_minutes = int((now - created_at).total_seconds() // 60)
        elif sender == "cliente":
            conversation.unread = True
    db.add(message)
    db.add(conversation)
    db.commit()
    db.refresh(message)
    return message
