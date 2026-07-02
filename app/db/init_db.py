from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.channel import Channel
from app.models.client import Client
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.quick_reply import QuickReply
from app.models.user import User
from app.services.clients import extract_first_name


CLIENT_COLUMNS = {
    "preferred_name": "VARCHAR(120)",
    "birth_date": "VARCHAR(20)",
    "gender": "VARCHAR(20)",
    "phone_country_code": "VARCHAR(8)",
    "phone_area_code": "VARCHAR(4)",
    "phone_number": "VARCHAR(20)",
    "cpf": "VARCHAR(30)",
    "rg": "VARCHAR(30)",
    "zip_code": "VARCHAR(20)",
    "address_number": "VARCHAR(30)",
    "address_complement": "VARCHAR(120)",
    "reference_point": "VARCHAR(160)",
    "fixed_location": "VARCHAR(255)",
    "restrictions": "TEXT",
    "complaints": "TEXT",
}


def ensure_client_columns(db: Session) -> None:
    existing = {row[1] for row in db.execute(text("PRAGMA table_info(clients)")).all()}
    for column, column_type in CLIENT_COLUMNS.items():
        if column not in existing:
            db.execute(text(f"ALTER TABLE clients ADD COLUMN {column} {column_type}"))
    db.commit()


def init_db(db: Session) -> None:
    ensure_client_columns(db)

    admin = db.query(User).filter(User.email == "admin@hub.local").first()
    if not admin:
        admin = User(
            name="Admin Ellub",
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
        db.add(QuickReply(title="Bom dia", shortcut="/bomdia", content="Ola, [nome_preferencial]! Me chamo [atendente] e sera um prazer te atender hoje.", type="global"))
    if not db.query(QuickReply).filter(QuickReply.shortcut == "/endereco").first():
        db.add(QuickReply(title="Confirmar endereco", shortcut="/endereco", content="Certo! A sua entrega sera para o endereco [endereco]?", type="global"))
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
