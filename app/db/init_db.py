from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models.channel import Channel
from app.models.client import Client
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.quick_reply import QuickReply
from app.models.user import User
from app.models.workspace import Workspace
from app.services.clients import extract_first_name


def init_db(db: Session) -> None:
    settings = get_settings()
    workspace = db.query(Workspace).filter(Workspace.slug == "ellub-demo").first()
    if not workspace:
        workspace = Workspace(name="Ellub Demo", slug="ellub-demo", is_active=True)
        db.add(workspace)
        db.flush()

    if not settings.demo_mode:
        db.commit()
        return

    admin = db.query(User).filter(User.email == "admin@hub.local", User.workspace_id == workspace.id).first()
    if not admin:
        admin = User(
            workspace_id=workspace.id,
            name="Admin Ellub",
            email="admin@hub.local",
            hashed_password=get_password_hash("admin123"),
            role="admin",
            is_active=True,
        )
        db.add(admin)

    ana = db.query(User).filter(User.email == "ana@hub.local", User.workspace_id == workspace.id).first()
    if not ana:
        ana = User(
            workspace_id=workspace.id,
            name="Ana Atendente",
            email="ana@hub.local",
            hashed_password=get_password_hash("ana123"),
            role="agent",
            is_active=True,
        )
        db.add(ana)

    bruno = db.query(User).filter(User.email == "bruno@hub.local", User.workspace_id == workspace.id).first()
    if not bruno:
        bruno = User(
            workspace_id=workspace.id,
            name="Bruno Atendente",
            email="bruno@hub.local",
            hashed_password=get_password_hash("bruno123"),
            role="agent",
            is_active=True,
        )
        db.add(bruno)
    db.flush()

    channels = [
        ("WhatsApp Principal", "WhatsApp"),
        ("Instagram Loja", "Instagram"),
        ("Facebook Pagina", "Facebook"),
    ]
    for name, type_ in channels:
        if not db.query(Channel).filter(Channel.workspace_id == workspace.id, Channel.name == name).first():
            db.add(Channel(workspace_id=workspace.id, name=name, type=type_))
    db.flush()

    if not db.query(QuickReply).filter(QuickReply.workspace_id == workspace.id, QuickReply.shortcut == "/bomdia").first():
        db.add(
            QuickReply(
                workspace_id=workspace.id,
                title="Bom dia",
                shortcut="/bomdia",
                content="Ola, [nome_preferencial]! Me chamo [atendente] e sera um prazer te atender hoje.",
                type="global",
            )
        )
    if not db.query(QuickReply).filter(QuickReply.workspace_id == workspace.id, QuickReply.shortcut == "/endereco").first():
        db.add(
            QuickReply(
                workspace_id=workspace.id,
                title="Confirmar endereco",
                shortcut="/endereco",
                content="Certo! A sua entrega sera para o endereco [endereco]?",
                type="global",
            )
        )
    db.flush()

    if not db.query(Client).filter(Client.workspace_id == workspace.id).first():
        client = Client(
            workspace_id=workspace.id,
            full_name="Isadora Alves Ribeiro",
            first_name=extract_first_name("Isadora Alves Ribeiro"),
            phone="+55 11 99999-0000",
            email="isadora@example.com",
            address="Rua das Flores, 123",
            notes="Cliente interessada em planos de suporte.",
        )
        db.add(client)
        db.flush()

        whatsapp = db.query(Channel).filter(Channel.workspace_id == workspace.id, Channel.type == "WhatsApp").first()
        conversation = Conversation(
            workspace_id=workspace.id,
            client_id=client.id,
            channel_id=whatsapp.id,
            agent_id=ana.id,
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
                Message(conversation_id=conversation.id, author_user_id=ana.id, sender="atendente", text="Bom dia, Isadora! Claro, vou te explicar.", status="enviada", created_at=datetime.utcnow() - timedelta(minutes=30)),
                Message(conversation_id=conversation.id, sender="cliente", text="Perfeito, obrigada.", status="recebida", created_at=datetime.utcnow() - timedelta(minutes=8)),
                Message(conversation_id=conversation.id, sender="sistema", text="Lead marcado como oportunidade.", status="lida", is_internal=True, created_at=datetime.utcnow() - timedelta(minutes=7)),
            ]
        )
        conversation.first_response_at = datetime.utcnow() - timedelta(minutes=30)
        conversation.first_response_minutes = 5

    db.commit()
