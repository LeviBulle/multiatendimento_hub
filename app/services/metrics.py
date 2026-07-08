from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.whatsapp_window_service import get_window_status, is_whatsapp_conversation


def get_admin_metrics(db: Session, workspace_id: int) -> dict:
    base = db.query(Conversation).filter(Conversation.workspace_id == workspace_id)
    open_conversations = base.filter(Conversation.status.in_(["aberta", "pendente"])).count()
    closed_conversations = base.filter(Conversation.status == "finalizada").count()
    avg_duration = (
        db.query(func.avg(Conversation.duration_minutes))
        .filter(Conversation.workspace_id == workspace_id, Conversation.duration_minutes.isnot(None))
        .scalar()
        or 0
    )
    avg_first_response = (
        db.query(func.avg(Conversation.first_response_minutes))
        .filter(Conversation.workspace_id == workspace_id, Conversation.first_response_minutes.isnot(None))
        .scalar()
        or 0
    )

    messages_by_agent = (
        db.query(User.name.label("name"), func.count(Message.id).label("total"))
        .join(Conversation, Conversation.agent_id == User.id)
        .join(Message, Message.conversation_id == Conversation.id)
        .filter(User.workspace_id == workspace_id, Conversation.workspace_id == workspace_id, Message.sender == "atendente")
        .group_by(User.name)
        .all()
    )
    conversations_by_channel = (
        db.query(Channel.name.label("name"), func.count(Conversation.id).label("total"))
        .join(Conversation, Conversation.channel_id == Channel.id)
        .filter(Channel.workspace_id == workspace_id, Conversation.workspace_id == workspace_id)
        .group_by(Channel.name)
        .all()
    )
    whatsapp_conversations = (
        db.query(Conversation)
        .join(Channel, Channel.id == Conversation.channel_id)
        .filter(Conversation.workspace_id == workspace_id, Channel.workspace_id == workspace_id)
        .all()
    )
    window_statuses = [get_window_status(item) for item in whatsapp_conversations if is_whatsapp_conversation(item)]
    return {
        "open_conversations": open_conversations,
        "closed_conversations": closed_conversations,
        "avg_duration_minutes": round(avg_duration, 1),
        "avg_first_response_minutes": round(avg_first_response, 1),
        "messages_by_agent": messages_by_agent,
        "conversations_by_channel": conversations_by_channel,
        "whatsapp_window_open": sum(status in {"active", "warning", "urgent"} for status in window_statuses),
        "whatsapp_window_urgent": sum(status == "urgent" for status in window_statuses),
        "whatsapp_window_closed": sum(status == "expired" for status in window_statuses),
        "whatsapp_waiting_customer": sum(status == "waiting_for_customer" for status in window_statuses),
    }
