from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.channel import Channel
from app.models.client import Client
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.quick_reply import QuickReply
from app.models.user import User
from app.services.clients import extract_first_name


def init_db(db: Session) -> None:
    admin = db.query(User).filter(User.email == "admin@hub.local").first()
    if not admin:
        admin = User(
            name="Admin Hub",
            email="admin@hub.local",
            hashed_password=get_password_hash("admin123"),
            role="admin",
            is_active=True,
        )
        db.add(admin)

    agent = db.query(User).filter(User.email == "ana@hub.local").first()
    if not agent:
        agent = User(
            name="Ana Atendente",
            email="ana@hub.local",
            hashed_password=get_password_hash("ana123"),
            role="agent",
            is_active=True,
        )
        db.add(agent)
    db.flush()

    channels = [
        ("WhatsApp Principal", "WhatsApp"),
        ("Instagram Loja", "Instagram"),
        ("Facebook Página", "Facebook"),
    ]
    for name, type_ in channels:
        if not db.query(Channel).filter(Channel.name == name).first():
            db.add(Channel(name=name, type=type_))
    db.flush()

    if not db.query(QuickReply).filter(QuickReply.shortcut == "/bomdia").first():
        db.add(QuickReply(title="Bom dia", shortcut="/bomdia", content="Bom dia, {primeiro_nome}! Como posso ajudar?", type="global"))
    if not db.query(QuickReply).filter(QuickReply.shortcut == "/obrigado").first():
        db.add(QuickReply(title="Agradecimento", shortcut="/obrigado", content="Obrigado pelo contato, {primeiro_nome}.", type="global"))
    db.flush()

    if not db.query(Client).first():
        client = Client(
            full_name="Isadora Alves Ribeiro",
            first_name=extract_first_name("Isadora Alves Ribeiro"),
            phone="+55 11 99999-0000",
            email="isadora@example.com",
            address="Rua das Flores, 123",
            notes="Cliente interessada em planos de suporte.",
        )
        db.add(client)
        db.flush()

        whatsapp = db.query(Channel).filter(Channel.type == "WhatsApp").first()
        conversation = Conversation(
            client_id=client.id,
            channel_id=whatsapp.id,
            agent_id=agent.id,
            status="aberta",
            unread=True,
            created_at=datetime.utcnow() - timedelta(minutes=35),
            last_message_at=datetime.utcnow() - timedelta(minutes=8),
        )
        db.add(conversation)
        db.flush()
        db.add_all(
            [
                Message(conversation_id=conversation.id, sender="cliente", text="Oi, queria saber mais sobre o atendimento.", status="recebida", created_at=datetime.utcnow() - timedelta(minutes=35)),
                Message(conversation_id=conversation.id, sender="atendente", text="Bom dia, Isadora! Claro, vou te explicar.", status="enviada", created_at=datetime.utcnow() - timedelta(minutes=30)),
                Message(conversation_id=conversation.id, sender="cliente", text="Perfeito, obrigada.", status="recebida", created_at=datetime.utcnow() - timedelta(minutes=8)),
                Message(conversation_id=conversation.id, sender="sistema", text="Lead marcado como oportunidade.", status="lida", is_internal=True, created_at=datetime.utcnow() - timedelta(minutes=7)),
            ]
        )
        conversation.first_response_at = datetime.utcnow() - timedelta(minutes=30)
        conversation.first_response_minutes = 5

    db.commit()
