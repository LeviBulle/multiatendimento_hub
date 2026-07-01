from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User


def get_admin_metrics(db: Session) -> dict:
    open_conversations = db.query(Conversation).filter(Conversation.status.in_(["aberta", "pendente"])).count()
    closed_conversations = db.query(Conversation).filter(Conversation.status == "finalizada").count()
    avg_duration = db.query(func.avg(Conversation.duration_minutes)).filter(Conversation.duration_minutes.isnot(None)).scalar() or 0
    avg_first_response = db.query(func.avg(Conversation.first_response_minutes)).filter(Conversation.first_response_minutes.isnot(None)).scalar() or 0

    messages_by_agent = (
        db.query(User.name.label("name"), func.count(Message.id).label("total"))
        .join(Conversation, Conversation.agent_id == User.id)
        .join(Message, Message.conversation_id == Conversation.id)
        .filter(Message.sender == "atendente")
        .group_by(User.name)
        .all()
    )
    conversations_by_channel = (
        db.query(Channel.name.label("name"), func.count(Conversation.id).label("total"))
        .join(Conversation, Conversation.channel_id == Channel.id)
        .group_by(Channel.name)
        .all()
    )
    return {
        "open_conversations": open_conversations,
        "closed_conversations": closed_conversations,
        "avg_duration_minutes": round(avg_duration, 1),
        "avg_first_response_minutes": round(avg_first_response, 1),
        "messages_by_agent": messages_by_agent,
        "conversations_by_channel": conversations_by_channel,
    }
