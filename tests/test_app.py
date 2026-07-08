from datetime import timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.core.time import as_utc, utc_now
from app.models.channel import Channel
from app.models.client import Client
from app.models.conversation import Conversation
from app.models.mention_notification import MentionNotification
from app.models.message import Message
from app.models.quick_reply import QuickReply
from app.models.user import User
from app.models.whatsapp_template import WhatsAppTemplate
from app.models.workspace import Workspace
from app.services.messages import create_message
from app.services.scheduled_messages import process_scheduled_messages
from app.services.whatsapp_window_service import get_window_expires_at, get_window_status

from conftest import create_admin, create_workspace, csrf, login, post_csrf


def test_valid_and_invalid_login(client):
    assert login(client).status_code == 303
    assert login(client, "admin@hub.local", "errada").status_code == 400


def test_inactive_user_cannot_authenticate(client, db):
    ana = db.query(User).filter(User.email == "ana@hub.local").one()
    ana.is_active = False
    db.commit()
    assert login(client, "ana@hub.local", "ana123").status_code == 400
    ana.is_active = True
    db.commit()


def test_agent_can_answer_other_agent_conversation_without_taking_ownership(client, db):
    ana = db.query(User).filter(User.email == "ana@hub.local").one()
    bruno = db.query(User).filter(User.email == "bruno@hub.local").one()
    conv = db.query(Conversation).filter(Conversation.agent_id == ana.id).first()
    assert login(client, "bruno@hub.local", "bruno123").status_code == 303
    token = csrf(client)
    response = client.post(
        f"/agent/conversations/{conv.id}/messages",
        data={"text": "Respondido pelo Bruno", "csrf_token": token},
        follow_redirects=False,
    )
    db.refresh(conv)
    message = db.query(Message).filter(Message.text == "Respondido pelo Bruno").one()
    assert response.status_code == 303
    assert conv.agent_id == ana.id
    assert message.author_user_id == bruno.id


def test_papagaio_demo_client_replies_to_agent_messages(client, db):
    conv = db.query(Conversation).join(Client).filter(Client.full_name == "Papagaio da Silva").one()
    login(client)
    response = post_csrf(client, f"/agent/conversations/{conv.id}/messages", {"text": "ola papagaio"})
    reply = db.query(Message).filter(Message.conversation_id == conv.id, Message.sender == "cliente").order_by(Message.id.desc()).first()
    assert response.status_code == 303
    assert reply.text == "loro quer biscoito"


def test_open_other_agent_conversation_does_not_change_responsible(client, db):
    ana = db.query(User).filter(User.email == "ana@hub.local").one()
    conv = db.query(Conversation).filter(Conversation.agent_id == ana.id).first()
    login(client, "bruno@hub.local", "bruno123")
    client.get(f"/agent/conversations/{conv.id}")
    db.refresh(conv)
    assert conv.agent_id == ana.id


def test_transfer_changes_responsible_and_creates_internal_record(client, db):
    bruno = db.query(User).filter(User.email == "bruno@hub.local").one()
    conv = db.query(Conversation).first()
    login(client)
    token = csrf(client)
    response = client.post(
        f"/agent/conversations/{conv.id}/transfer",
        data={"agent_id": bruno.id, "csrf_token": token},
        follow_redirects=False,
    )
    db.refresh(conv)
    note = db.query(Message).filter(Message.conversation_id == conv.id, Message.is_internal.is_(True)).order_by(Message.id.desc()).first()
    assert response.status_code == 303
    assert conv.agent_id == bruno.id
    assert "transferiu o atendimento" in note.text


def test_other_workspace_cannot_access_core_resources(client, db):
    other = Workspace(name="Outra Empresa", slug="outra", is_active=True)
    db.add(other)
    db.flush()
    intruder = User(workspace_id=other.id, name="Intruso", email="intruso@hub.local", hashed_password=get_password_hash("123456"), role="admin", is_active=True)
    db.add(intruder)
    db.commit()
    conv = db.query(Conversation).filter(Conversation.workspace_id != other.id).first()

    login(client, "intruso@hub.local", "123456")
    token = csrf(client)
    assert "Nenhuma conversa encontrada" in client.get(f"/agent/conversations/{conv.id}").text
    assert client.post(f"/agent/conversations/{conv.id}/messages", data={"text": "x", "csrf_token": token}, follow_redirects=False).status_code == 303
    assert client.post(f"/agent/conversations/{conv.id}/status", data={"status": "finalizada", "csrf_token": token}, follow_redirects=False).status_code == 303
    assert "<td>WhatsApp Principal</td>" not in client.get("/admin/channels").text
    assert "Ana Atendente" not in client.get("/admin/users").text


def test_admin_manages_only_own_workspace_users(client):
    login(client)
    assert "Ana Atendente" in client.get("/admin/users").text
    assert "Intruso" not in client.get("/admin/users").text


def test_unread_favorite_and_expired_filters(client, db):
    conv = db.query(Conversation).first()
    conv.unread = True
    conv.is_favorite = True
    conv.first_response_at = None
    conv.created_at = utc_now() - timedelta(minutes=60)
    conv.status = "aberta"
    db.commit()
    login(client)
    rendered_name = conv.client.full_name.upper()
    assert rendered_name in client.get("/agent?unread=1").text
    assert rendered_name in client.get("/agent?favorites=1").text
    assert rendered_name in client.get("/agent?expired=1").text


def test_opening_conversation_keeps_unread_until_agent_replies(client, db):
    conv = db.query(Conversation).first()
    conv.unread = True
    conv.status = "aberta"
    db.commit()

    login(client)
    page = client.get(f"/agent/conversations/{conv.id}")
    db.refresh(conv)
    assert page.status_code == 200
    assert conv.unread is True

    token = csrf(client)
    response = client.post(
        f"/agent/conversations/{conv.id}/messages",
        data={"text": "Resposta do atendimento", "csrf_token": token},
        follow_redirects=False,
    )
    db.refresh(conv)
    assert response.status_code == 303
    assert conv.unread is False


def test_invalid_upload_is_blocked(client, db):
    conv = db.query(Conversation).first()
    login(client)
    token = csrf(client)
    response = client.post(
        f"/agent/conversations/{conv.id}/messages",
        data={"text": "", "csrf_token": token},
        files={"attachment": ("bad.exe", BytesIO(b"x"), "application/octet-stream")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "Tipo+de+arquivo" in response.headers["location"]


def test_upload_above_size_is_blocked(client, db, monkeypatch):
    conv = db.query(Conversation).first()
    login(client)
    token = csrf(client)
    get_settings.cache_clear()
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
    uploads_before = set(Path("app/static/uploads").iterdir())
    mensagens_antes = db.query(Message).filter(Message.conversation_id == conv.id).count()
    response = client.post(
        f"/agent/conversations/{conv.id}/messages",
        data={"text": "", "csrf_token": token},
        files={"attachment": ("big.pdf", BytesIO(b"x" * (1024 * 1024 + 1)), "application/pdf")},
        follow_redirects=True,
    )
    get_settings.cache_clear()
    mensagens_depois = db.query(Message).filter(Message.conversation_id == conv.id).count()
    uploads_depois = set(Path("app/static/uploads").iterdir())
    assert response.status_code == 200
    assert "Arquivo maior que o limite" in response.text
    assert mensagens_depois == mensagens_antes
    assert uploads_depois == uploads_before


def test_upload_blocks_disallowed_mime_and_extension(client, db):
    conv = db.query(Conversation).first()
    login(client)
    before = db.query(Message).filter(Message.conversation_id == conv.id).count()

    bad_mime = post_csrf(
        client,
        f"/agent/conversations/{conv.id}/messages",
        {"text": ""},
        files={"attachment": ("arquivo.pdf", BytesIO(b"x"), "text/plain")},
    )
    bad_extension = post_csrf(
        client,
        f"/agent/conversations/{conv.id}/messages",
        {"text": ""},
        files={"attachment": ("arquivo.exe", BytesIO(b"x"), "application/pdf")},
    )

    assert "Tipo+de+arquivo" in bad_mime.headers["location"]
    assert "Tipo+de+arquivo" in bad_extension.headers["location"]
    assert db.query(Message).filter(Message.conversation_id == conv.id).count() == before


def test_allowed_upload_uses_uuid_physical_name(client, db):
    conv = db.query(Conversation).first()
    login(client)
    original_name = "contrato cliente.pdf"
    response = post_csrf(
        client,
        f"/agent/conversations/{conv.id}/messages",
        {"text": ""},
        files={"attachment": (original_name, BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    message = db.query(Message).filter(Message.attachment_original_name == original_name).order_by(Message.id.desc()).first()
    stored_path = Path("app/static/uploads") / message.attachment_stored_name
    try:
        assert response.status_code == 303
        assert message.attachment_stored_name != original_name
        assert UUID(Path(message.attachment_stored_name).stem)
        assert stored_path.exists()
    finally:
        stored_path.unlink(missing_ok=True)


def test_admin_forms_require_and_accept_csrf(client, db):
    login(client)
    actions = [
        ("/admin/users", {"name": "Carlos Agente", "email": "carlos@example.com", "password": "123456", "is_active": "true"}, User, "carlos@example.com"),
        ("/admin/channels", {"name": "WhatsApp CSRF", "type": "WhatsApp"}, Channel, "WhatsApp CSRF"),
        ("/admin/clients", {"full_name": "Cliente CSRF"}, Client, "Cliente CSRF"),
        ("/admin/quick-replies", {"title": "Oi", "shortcut": "/oi-csrf", "content": "Ola"}, QuickReply, "/oi-csrf"),
    ]
    for url, data, _model, _value in actions:
        assert client.post(url, data=data, follow_redirects=False).status_code == 403
        assert post_csrf(client, url, data).status_code == 303

    assert db.query(User).filter(User.email == "carlos@example.com").first()
    assert db.query(Channel).filter(Channel.name == "WhatsApp CSRF").first()
    assert db.query(Client).filter(Client.full_name == "CLIENTE CSRF").first()
    assert db.query(QuickReply).filter(QuickReply.shortcut == "/oi-csrf").first()


def test_agent_cannot_execute_admin_actions_even_with_csrf(client):
    login(client, "ana@hub.local", "ana123")
    response = post_csrf(client, "/admin/channels", {"name": "Canal Indevido", "type": "WhatsApp"})
    assert response.status_code == 403


def test_admin_cannot_mutate_other_workspace_admin_data(client, db):
    other = create_workspace(db, "Outra CSRF", "outra-csrf")
    create_admin(db, other, "admin-outra-csrf@hub.local")
    channel = db.query(Channel).filter(Channel.workspace_id != other.id).first()
    reply = db.query(QuickReply).filter(QuickReply.workspace_id != other.id, QuickReply.type == "global").first()
    original_channel_name = channel.name
    original_reply_count = db.query(QuickReply).filter(QuickReply.workspace_id != other.id).count()

    login(client, "admin-outra-csrf@hub.local", "123456")
    assert f"<td>{original_channel_name}</td>" not in client.get("/admin/channels").text
    post_csrf(client, f"/admin/channels/{channel.id}/edit", {"name": "Invadido", "type": "WhatsApp"})
    post_csrf(client, f"/admin/quick-replies/{reply.id}/delete", {})
    db.refresh(channel)

    assert channel.name == original_channel_name
    assert db.query(QuickReply).filter(QuickReply.workspace_id != other.id).count() == original_reply_count


def test_admin_can_create_unassigned_conversation(client, db):
    channel = db.query(Channel).first()
    login(client)
    response = post_csrf(
        client,
        "/agent/conversations",
        {"full_name": "Cliente sem responsavel", "channel_id": str(channel.id), "agent_id": "", "initial_message": ""},
    )
    conversation = db.query(Conversation).join(Client).filter(Client.full_name == "CLIENTE SEM RESPONSAVEL").one()
    assert response.status_code == 303
    assert conversation.agent_id is None


def test_scheduled_message_processing_is_idempotent(db):
    conv = db.query(Conversation).first()
    message = create_message(db, conv, "atendente", "mensagem agendada", scheduled_for=utc_now() - timedelta(minutes=1), author_user_id=conv.agent_id)
    assert message.status == "enviada"

    scheduled = Message(
        conversation_id=conv.id,
        author_user_id=conv.agent_id,
        sender="atendente",
        text="processar uma vez",
        status="agendada",
        scheduled_for=utc_now() - timedelta(minutes=1),
    )
    db.add(scheduled)
    db.commit()

    assert process_scheduled_messages(db) == 1
    assert process_scheduled_messages(db) == 0
    db.refresh(scheduled)
    assert scheduled.status == "enviada"


def test_whatsapp_window_starts_and_is_not_reset_by_agent_or_internal_note(db):
    conv = db.query(Conversation).join(Channel).filter(Channel.type == "WhatsApp").first()
    conv.last_customer_message_at = None
    db.commit()

    assert get_window_status(conv) == "waiting_for_customer"
    customer_time = utc_now() - timedelta(hours=2)
    create_message(db, conv, "cliente", "oi", status_override="enviada")
    db.refresh(conv)
    first_window = conv.last_customer_message_at

    assert get_window_status(conv) == "active"
    assert round((get_window_expires_at(conv) - as_utc(first_window)).total_seconds()) == 24 * 60 * 60

    create_message(db, conv, "atendente", "resposta")
    create_message(db, conv, "sistema", "nota", is_internal=True)
    db.refresh(conv)
    assert conv.last_customer_message_at == first_window

    conv.last_customer_message_at = customer_time
    db.commit()
    create_message(db, conv, "cliente", "nova resposta")
    db.refresh(conv)
    assert as_utc(conv.last_customer_message_at) > customer_time


def test_expired_whatsapp_window_blocks_freeform_audio_and_attachment(client, db):
    conv = db.query(Conversation).join(Channel).filter(Channel.type == "WhatsApp").first()
    conv.last_customer_message_at = utc_now() - timedelta(hours=25)
    db.commit()
    login(client)
    before_messages = db.query(Message).filter(Message.conversation_id == conv.id).count()
    before_files = set(Path("app/static/uploads").iterdir())

    text_response = post_csrf(client, f"/agent/conversations/{conv.id}/messages", {"text": "livre"})
    audio_response = post_csrf(
        client,
        f"/agent/conversations/{conv.id}/messages",
        {"text": ""},
        files={"attachment": ("audio.webm", BytesIO(b"audio"), "audio/webm")},
    )
    attachment_response = post_csrf(
        client,
        f"/agent/conversations/{conv.id}/messages",
        {"text": ""},
        files={"attachment": ("doc.pdf", BytesIO(b"%PDF"), "application/pdf")},
    )

    assert "janela+de+atendimento+do+WhatsApp+expirou" in text_response.headers["location"]
    assert "janela+de+atendimento+do+WhatsApp+expirou" in audio_response.headers["location"]
    assert "janela+de+atendimento+do+WhatsApp+expirou" in attachment_response.headers["location"]
    assert db.query(Message).filter(Message.conversation_id == conv.id).count() == before_messages
    assert set(Path("app/static/uploads").iterdir()) == before_files


def test_expired_whatsapp_window_allows_internal_notes(client, db):
    conv = db.query(Conversation).join(Channel).filter(Channel.type == "WhatsApp").first()
    conv.last_customer_message_at = utc_now() - timedelta(hours=25)
    db.commit()
    login(client)
    before_messages = db.query(Message).filter(Message.conversation_id == conv.id).count()

    response = post_csrf(
        client,
        f"/agent/conversations/{conv.id}/messages",
        {"text": "nota interna com janela vencida", "is_internal": "true"},
    )

    note = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id, Message.text == "nota interna com janela vencida")
        .one()
    )
    assert response.status_code == 303
    assert note.is_internal is True
    assert note.sender == "sistema"
    assert db.query(Message).filter(Message.conversation_id == conv.id).count() == before_messages + 1


def test_approved_template_can_be_sent_after_expiration_without_reopening_window(client, db):
    conv = db.query(Conversation).join(Channel).filter(Channel.type == "WhatsApp").first()
    conv.last_customer_message_at = utc_now() - timedelta(hours=25)
    template = WhatsAppTemplate(
        workspace_id=conv.workspace_id,
        name="teste_template_expirado",
        slug="teste_template_expirado",
        language="pt_BR",
        category="utility",
        content="Ola, {{cliente_nome}}.",
        status="approved",
    )
    db.add(template)
    db.commit()
    original_window = conv.last_customer_message_at

    login(client)
    response = post_csrf(client, f"/agent/conversations/{conv.id}/templates", {"template_id": str(template.id)})
    message = db.query(Message).filter(Message.whatsapp_template_id == template.id).order_by(Message.id.desc()).first()
    db.refresh(conv)

    assert response.status_code == 303
    assert message is not None
    assert message.message_kind == "template"
    assert conv.last_customer_message_at == original_window
    assert get_window_status(conv) == "expired"

    create_message(db, conv, "cliente", "respondi ao modelo")
    db.refresh(conv)
    assert get_window_status(conv) == "active"


def test_template_from_other_workspace_or_not_approved_cannot_be_sent(client, db):
    conv = db.query(Conversation).join(Channel).filter(Channel.type == "WhatsApp").first()
    other = create_workspace(db, "Templates Outro", "templates-outro")
    foreign = WhatsAppTemplate(workspace_id=other.id, name="externo", slug="externo", content="Oi", status="approved")
    draft = WhatsAppTemplate(workspace_id=conv.workspace_id, name="rascunho", slug="rascunho", content="Oi", status="draft")
    db.add_all([foreign, draft])
    db.commit()
    login(client)

    foreign_response = post_csrf(client, f"/agent/conversations/{conv.id}/templates", {"template_id": str(foreign.id)})
    draft_response = post_csrf(client, f"/agent/conversations/{conv.id}/templates", {"template_id": str(draft.id)})

    assert "Modelo+WhatsApp+indisponivel" in foreign_response.headers["location"]
    assert "Modelo+WhatsApp+indisponivel" in draft_response.headers["location"]


def test_instagram_and_facebook_are_not_blocked_by_whatsapp_window(client, db):
    workspace_id = db.query(Workspace).filter(Workspace.slug == "ellub-demo").one().id
    admin = db.query(User).filter(User.email == "admin@hub.local").one()
    for channel_type in ("Instagram", "Facebook"):
        channel = db.query(Channel).filter(Channel.workspace_id == workspace_id, Channel.type == channel_type).first()
        client_obj = Client(workspace_id=workspace_id, full_name=f"{channel_type} CLIENTE", first_name=channel_type)
        db.add(client_obj)
        db.flush()
        conv = Conversation(workspace_id=workspace_id, client_id=client_obj.id, channel_id=channel.id, agent_id=admin.id, last_customer_message_at=utc_now() - timedelta(days=3))
        db.add(conv)
        db.commit()
        login(client)
        response = post_csrf(client, f"/agent/conversations/{conv.id}/messages", {"text": f"livre {channel_type}"})
        assert response.status_code == 303
        assert db.query(Message).filter(Message.conversation_id == conv.id, Message.text == f"livre {channel_type}").first()


def test_scheduled_freeform_is_blocked_if_window_closes_before_processing(db):
    conv = db.query(Conversation).join(Channel).filter(Channel.type == "WhatsApp").first()
    conv.last_customer_message_at = utc_now() - timedelta(hours=25)
    scheduled = Message(
        conversation_id=conv.id,
        author_user_id=conv.agent_id,
        sender="atendente",
        text="agendada livre",
        status="agendada",
        message_kind="text",
        scheduled_for=utc_now() - timedelta(minutes=1),
    )
    db.add(scheduled)
    db.commit()

    assert process_scheduled_messages(db) == 1
    db.refresh(scheduled)
    assert scheduled.status == "blocked_by_whatsapp_window"
    assert "janela de atendimento do WhatsApp expirou" in scheduled.failure_reason


def test_invalid_schedule_date_and_invalid_status_are_friendly(client, db):
    conv = db.query(Conversation).first()
    conv.last_customer_message_at = utc_now()
    db.commit()
    login(client)
    token = csrf(client)
    bad_date = client.post(
        f"/agent/conversations/{conv.id}/messages",
        data={"text": "oi", "scheduled_for": "data ruim", "csrf_token": token},
        follow_redirects=False,
    )
    bad_status = client.post(
        f"/agent/conversations/{conv.id}/status",
        data={"status": "sumiu", "csrf_token": token},
        follow_redirects=False,
    )
    assert "Data+de+agendamento+invalida" in bad_date.headers["location"]
    assert "Status+invalido" in bad_status.headers["location"]


def test_internal_mention_creates_notification_and_can_be_read(client, db):
    bruno = db.query(User).filter(User.email == "bruno@hub.local").one()
    conv = db.query(Conversation).first()
    login(client)
    token = csrf(client)
    response = client.post(
        f"/agent/conversations/{conv.id}/messages",
        data={"text": "@Bruno Atendente veja este atendimento", "is_internal": "true", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    notification = (
        db.query(MentionNotification)
        .filter(MentionNotification.mentioned_user_id == bruno.id, MentionNotification.conversation_id == conv.id)
        .order_by(MentionNotification.id.desc())
        .first()
    )
    assert notification is not None
    assert notification.is_read is False

    login(client, "bruno@hub.local", "bruno123")
    page = client.get("/agent").text
    assert "Mencoes internas" in page
    assert "veja este atendimento" in page
    token = csrf(client)
    read_response = client.post(
        f"/agent/notifications/{notification.id}/read",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    db.refresh(notification)
    assert read_response.status_code == 303
    assert read_response.headers["location"] == f"/agent/conversations/{conv.id}"
    assert notification.is_read is True


def test_user_can_update_availability(client, db):
    ana = db.query(User).filter(User.email == "ana@hub.local").one()
    login(client, "ana@hub.local", "ana123")
    token = csrf(client)
    response = client.post(
        "/profile/availability",
        data={"is_available": "false", "next_url": "/agent/conversations/1", "csrf_token": token},
        follow_redirects=False,
    )
    db.refresh(ana)
    assert response.status_code == 303
    assert response.headers["location"] == "/agent/conversations/1"
    assert ana.is_available is False
