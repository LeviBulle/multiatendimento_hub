from sqlalchemy.orm import Session

from app.core.time import as_utc, utc_now
from app.models.message import Message
from app.services.whatsapp_window_service import WHATSAPP_WINDOW_ERROR, can_send_freeform_message


def process_scheduled_messages(db: Session) -> int:
    """Publish due scheduled messages once.

    MVP processing still runs from the conversation screen. The service boundary
    keeps the route light and makes it straightforward to move this to a worker.
    """
    now = utc_now()
    messages = db.query(Message).filter(Message.status == "agendada", Message.scheduled_for <= now).all()
    processed = 0
    for message in messages:
        if message.status != "agendada":
            continue
        try:
            conversation = message.conversation
            if message.message_kind != "template" and not can_send_freeform_message(conversation, now):
                message.status = "blocked_by_whatsapp_window"
                message.failure_reason = WHATSAPP_WINDOW_ERROR
                processed += 1
                continue
            message.status = "enviada"
            message.created_at = now
            conversation.last_message_at = now
            if message.sender == "atendente":
                conversation.unread = False
                if conversation.first_response_at is None:
                    conversation.first_response_at = now
                    created_at = as_utc(conversation.created_at) or now
                    conversation.first_response_minutes = int((now - created_at).total_seconds() // 60)
            processed += 1
        except Exception:
            message.status = "failed"
    db.commit()
    return processed
