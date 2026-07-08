from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.core.time import utc_now
from app.models.channel import Channel
from app.models.client import Client
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.quick_reply import QuickReply
from app.models.user import User
from app.models.whatsapp_template import WhatsAppTemplate
from app.models.workspace import Workspace
from app.services.clients import extract_first_name
from app.services.demo_auto_reply import PAPAGAIO_CLIENT_NAME


def init_db(db: Session) -> None:
    settings = get_settings()
    if not settings.demo_mode:
        db.commit()
        return

    workspace = db.query(Workspace).filter(Workspace.slug == "ellub-demo").first()
    if not workspace:
        workspace = Workspace(name="Ellub Demo", slug="ellub-demo", is_active=True)
        db.add(workspace)
        db.flush()

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

    if not db.query(WhatsAppTemplate).filter(WhatsAppTemplate.workspace_id == workspace.id, WhatsAppTemplate.name == "reabertura_atendimento").first():
        db.add(
            WhatsAppTemplate(
                workspace_id=workspace.id,
                name="reabertura_atendimento",
                slug="reabertura_atendimento",
                language="pt_BR",
                category="utility",
                content="Ola, {{cliente_nome}}. Estamos retomando seu atendimento. Como podemos ajudar?",
                status="approved",
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
            created_at=utc_now() - timedelta(minutes=35),
            last_message_at=utc_now() - timedelta(minutes=8),
            last_customer_message_at=utc_now() - timedelta(minutes=8),
        )
        db.add(conversation)
        db.flush()
        db.add_all(
            [
                Message(conversation_id=conversation.id, sender="cliente", text="Oi, queria saber mais sobre o atendimento.", status="recebida", created_at=utc_now() - timedelta(minutes=35)),
                Message(conversation_id=conversation.id, author_user_id=ana.id, sender="atendente", text="Bom dia, Isadora! Claro, vou te explicar.", status="enviada", created_at=utc_now() - timedelta(minutes=30)),
                Message(conversation_id=conversation.id, sender="cliente", text="Perfeito, obrigada.", status="recebida", created_at=utc_now() - timedelta(minutes=8)),
                Message(conversation_id=conversation.id, sender="sistema", text="Lead marcado como oportunidade.", status="lida", is_internal=True, created_at=utc_now() - timedelta(minutes=7)),
            ]
        )
        conversation.first_response_at = utc_now() - timedelta(minutes=30)
        conversation.first_response_minutes = 5

    whatsapp = db.query(Channel).filter(Channel.workspace_id == workspace.id, Channel.type == "WhatsApp").first()
    ana = db.query(User).filter(User.email == "ana@hub.local", User.workspace_id == workspace.id).first()
    papagaio = db.query(Client).filter(Client.workspace_id == workspace.id, Client.full_name == PAPAGAIO_CLIENT_NAME).first()
    if not papagaio:
        papagaio = Client(
            workspace_id=workspace.id,
            full_name=PAPAGAIO_CLIENT_NAME,
            first_name=extract_first_name(PAPAGAIO_CLIENT_NAME),
            phone="+55 11 91000-2222",
            notes="Cliente demo com resposta automatica para testes.",
        )
        db.add(papagaio)
        db.flush()
    if whatsapp and ana and not db.query(Conversation).filter(Conversation.workspace_id == workspace.id, Conversation.client_id == papagaio.id).first():
        papagaio_conversation = Conversation(
            workspace_id=workspace.id,
            client_id=papagaio.id,
            channel_id=whatsapp.id,
            agent_id=ana.id,
            status="aberta",
            unread=True,
            created_at=utc_now(),
            last_message_at=utc_now(),
            last_customer_message_at=utc_now(),
        )
        db.add(papagaio_conversation)
        db.flush()
        db.add(
            Message(
                conversation_id=papagaio_conversation.id,
                sender="cliente",
                text="loro quer biscoito",
                status="recebida",
                created_at=utc_now(),
            )
        )

    db.commit()
