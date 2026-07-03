from datetime import datetime, timedelta
from io import BytesIO

from app.core.security import get_password_hash
from app.models.conversation import Conversation
from app.models.mention_notification import MentionNotification
from app.models.message import Message
from app.models.user import User
from app.models.workspace import Workspace

from conftest import csrf, login


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
    conv.created_at = datetime.utcnow() - timedelta(minutes=60)
    conv.status = "aberta"
    db.commit()
    login(client)
    assert conv.client.full_name in client.get("/agent?unread=1").text
    assert conv.client.full_name in client.get("/agent?favorites=1").text
    assert conv.client.full_name in client.get("/agent?expired=1").text


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
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
    response = client.post(
        f"/agent/conversations/{conv.id}/messages",
        data={"text": "", "csrf_token": token},
        files={"attachment": ("big.pdf", BytesIO(b"x" * (1024 * 1024 + 1)), "application/pdf")},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_invalid_schedule_date_and_invalid_status_are_friendly(client, db):
    conv = db.query(Conversation).first()
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
