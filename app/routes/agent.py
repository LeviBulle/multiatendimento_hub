from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.deps import get_current_user, get_workspace_channel, get_workspace_conversation, get_workspace_user
from app.db.session import get_db
from app.models.channel import Channel
from app.models.client import Client
from app.models.conversation import Conversation
from app.models.mention_notification import MentionNotification
from app.models.quick_reply import QuickReply
from app.models.user import User
from app.services.clients import upsert_client_fields
from app.services.mentions import create_mention_notifications, notification_context
from app.services.messages import create_message, process_scheduled_messages
from app.services.quick_replies import normalize_shortcut, render_template
from app.services.uploads import validate_and_store_upload

router = APIRouter(prefix="/agent")
templates = Jinja2Templates(directory="app/templates")
VALID_STATUSES = {"aberta", "pendente", "finalizada"}


def parse_int(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def parse_int_list(values: list[str]) -> list[int]:
    parsed = []
    for value in values:
        item = parse_int(value)
        if item is not None:
            parsed.append(item)
    return parsed


def human_delta(value: datetime | None) -> str:
    if not value:
        return "sem mensagens"
    minutes = int((datetime.utcnow() - value).total_seconds() // 60)
    if minutes < 1:
        return "agora"
    if minutes < 60:
        return f"{minutes}min"
    return f"{minutes // 60}h"


def message_preview(conversation: Conversation) -> tuple[str, str | None]:
    if not conversation.messages:
        return "Sem mensagens", None
    message = conversation.messages[-1]
    if message.attachment_original_name and not message.text:
        preview = f"Anexo: {message.attachment_original_name}"
    elif message.attachment_original_name:
        preview = f"{message.text.strip()} · Anexo"
    elif message.is_internal:
        preview = f"Nota interna: {message.text.strip()}"
    else:
        preview = message.text.strip()
    return (preview or "Mensagem sem texto", message.sender)


def is_expired_expr():
    settings = get_settings()
    limit = datetime.utcnow().timestamp() - (settings.response_sla_minutes * 60)
    return datetime.fromtimestamp(limit)


def apply_common_filters(query, search: str, channel_ids: list[int], unread: bool, favorites: bool, expired: bool):
    search = search.strip()
    if search:
        like = f"%{search}%"
        query = query.join(Conversation.client).filter(
            or_(
                Client.full_name.ilike(like),
                Client.first_name.ilike(like),
                Client.phone.ilike(like),
                Client.email.ilike(like),
            )
        )
    if channel_ids:
        query = query.filter(Conversation.channel_id.in_(channel_ids))
    if unread:
        query = query.filter(Conversation.unread.is_(True))
    if favorites:
        query = query.filter(Conversation.is_favorite.is_(True))
    if expired:
        query = query.filter(
            Conversation.status.in_(["aberta", "pendente"]),
            Conversation.first_response_at.is_(None),
            Conversation.created_at < is_expired_expr(),
        )
    return query


def chat_context(
    request: Request,
    db: Session,
    current_user: User,
    conversation_id: int | None = None,
    search: str = "",
    tab: str = "atendimentos",
    agent_ids: list[int] | None = None,
    channel_ids: list[int] | None = None,
    unread: bool = False,
    expired: bool = False,
    favorites: bool = False,
) -> dict:
    process_scheduled_messages(db)
    tabs = {"novo", "atendimentos", "nao_lidos", "encerrados"}
    tab = tab if tab in tabs else "atendimentos"
    workspace_id = current_user.workspace_id

    agents = (
        db.query(User)
        .filter(User.workspace_id == workspace_id, User.role == "agent", User.is_active.is_(True))
        .order_by(User.name)
        .all()
    )
    mention_users = (
        db.query(User)
        .filter(
            User.workspace_id == workspace_id,
            User.is_active.is_(True),
            User.id != current_user.id,
            or_(User.role == "agent", User.role == "admin"),
        )
        .order_by(User.name)
        .all()
    )
    valid_agent_ids = {agent.id for agent in agents}
    selected_agent_ids = [agent_id for agent_id in (agent_ids or []) if agent_id in valid_agent_ids]
    if current_user.role != "admin" and not selected_agent_ids:
        selected_agent_ids = [current_user.id]

    channels = (
        db.query(Channel)
        .filter(Channel.workspace_id == workspace_id, Channel.is_active.is_(True))
        .order_by(Channel.type, Channel.name)
        .all()
    )
    valid_channel_ids = {channel.id for channel in channels}
    selected_channel_ids = [channel_id for channel_id in (channel_ids or []) if channel_id in valid_channel_ids]

    query = (
        db.query(Conversation)
        .options(joinedload(Conversation.client), joinedload(Conversation.channel), joinedload(Conversation.agent))
        .filter(Conversation.workspace_id == workspace_id)
    )
    query = apply_common_filters(query, search, selected_channel_ids, unread, favorites, expired)

    def apply_agent_filter(base_query):
        if selected_agent_ids:
            return base_query.filter(Conversation.agent_id.in_(selected_agent_ids))
        return base_query

    if tab == "novo":
        query = query.filter(Conversation.agent_id.is_(None), Conversation.status != "finalizada")
    elif tab == "atendimentos":
        query = apply_agent_filter(query).filter(Conversation.status.in_(["aberta", "pendente"]))
    elif tab == "nao_lidos":
        query = apply_agent_filter(query).filter(Conversation.unread.is_(True), Conversation.status != "finalizada")
    elif tab == "encerrados":
        query = apply_agent_filter(query).filter(Conversation.status == "finalizada")

    count_query = db.query(Conversation).filter(Conversation.workspace_id == workspace_id)
    count_query = apply_common_filters(count_query, search, selected_channel_ids, unread, favorites, expired)
    status_counts = {
        "novo": count_query.filter(Conversation.agent_id.is_(None), Conversation.status != "finalizada").count(),
        "atendimentos": apply_agent_filter(count_query).filter(Conversation.status.in_(["aberta", "pendente"])).count(),
        "nao_lidos": apply_agent_filter(count_query).filter(Conversation.unread.is_(True), Conversation.status != "finalizada").count(),
        "encerrados": apply_agent_filter(count_query).filter(Conversation.status == "finalizada").count(),
    }

    conversations = query.order_by(Conversation.last_message_at.desc(), Conversation.created_at.desc()).all()
    for item in conversations:
        item.time_since_last = human_delta(item.last_message_at)
        item.is_expired = item.status in {"aberta", "pendente"} and item.first_response_at is None and item.created_at < is_expired_expr()
        item.last_preview, item.last_sender = message_preview(item)

    conversation = None
    if conversation_id:
        conversation = get_workspace_conversation(db, current_user, conversation_id)
    elif conversations:
        conversation = conversations[0]
    messages = conversation.messages if conversation else []

    quick_replies = []
    shortcuts = {}
    if conversation:
        replies = (
            db.query(QuickReply)
            .filter(
                QuickReply.workspace_id == workspace_id,
                or_(QuickReply.type == "global", QuickReply.owner_id == current_user.id),
            )
            .order_by(QuickReply.type, QuickReply.shortcut)
            .all()
        )
        for reply in replies:
            rendered = render_template(reply.content, conversation.client, current_user)
            quick_replies.append({"shortcut": reply.shortcut, "rendered": rendered})
            shortcuts[reply.shortcut] = rendered

    base_params = {"tab": tab}
    if selected_agent_ids:
        base_params["agent_id"] = selected_agent_ids
    if selected_channel_ids:
        base_params["channel_id"] = selected_channel_ids
    if search:
        base_params["q"] = search
    if unread:
        base_params["unread"] = "1"
    if expired:
        base_params["expired"] = "1"
    if favorites:
        base_params["favorites"] = "1"

    def build_query(**overrides) -> str:
        params = {**base_params, **overrides}
        params = {key: value for key, value in params.items() if value not in (None, "", [], False)}
        return urlencode(params, doseq=True)

    context = {
        "request": request,
        "current_user": current_user,
        "conversations": conversations,
        "conversation": conversation,
        "messages": messages,
        "channels": channels,
        "agents": agents,
        "mention_users": [{"name": user.name, "insert": f"@{user.name}"} for user in mention_users],
        "quick_replies": quick_replies,
        "shortcuts": shortcuts,
        "filters": {
            "search": search,
            "tab": tab,
            "agent_ids": selected_agent_ids,
            "channel_ids": selected_channel_ids,
            "unread": unread,
            "expired": expired,
            "favorites": favorites,
        },
        "error": request.query_params.get("error", ""),
        "status_options": ["aberta", "pendente", "finalizada"],
        "status_counts": status_counts,
        "tab_urls": {name: f"/agent?{build_query(tab=name)}" for name in tabs},
        "list_query": build_query(),
        "agent_filter_options": agents,
        "demo_mode": get_settings().demo_mode,
    }
    context.update(notification_context(db, current_user))
    return context


def request_filters(request: Request) -> dict:
    return {
        "search": request.query_params.get("q", ""),
        "tab": request.query_params.get("tab", "atendimentos"),
        "agent_ids": parse_int_list(request.query_params.getlist("agent_id")),
        "channel_ids": parse_int_list(request.query_params.getlist("channel_id")),
        "unread": request.query_params.get("unread") == "1",
        "expired": request.query_params.get("expired") == "1",
        "favorites": request.query_params.get("favorites") == "1",
    }


@router.get("")
def agent_home(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "agent/chat.html", chat_context(request, db, current_user, **request_filters(request)))


@router.get("/conversations/{conversation_id}")
def conversation_page(conversation_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversation = get_workspace_conversation(db, current_user, conversation_id)
    if conversation:
        if conversation.agent_id is None and current_user.role == "agent":
            conversation.agent_id = current_user.id
        db.commit()
    return templates.TemplateResponse(
        request,
        "agent/chat.html",
        chat_context(request, db, current_user, conversation_id=conversation_id, **request_filters(request)),
    )


@router.post("/conversations")
def create_conversation(
    full_name: str = Form(...),
    channel_id: int = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    initial_message: str = Form(""),
    agent_id: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    channel = get_workspace_channel(db, current_user, channel_id)
    if not channel or not channel.is_active:
        return RedirectResponse("/agent?error=Canal+inexistente+ou+inativo.", status_code=303)

    owner_id = current_user.id
    if agent_id:
        target = get_workspace_user(db, current_user, agent_id)
        if target and target.is_active and target.role == "agent":
            owner_id = target.id

    client = Client(full_name="", first_name="", workspace_id=current_user.workspace_id)
    upsert_client_fields(client, full_name, phone, email, "", "")
    db.add(client)
    db.flush()

    conversation = Conversation(
        workspace_id=current_user.workspace_id,
        client_id=client.id,
        channel_id=channel.id,
        agent_id=owner_id,
        status="aberta",
        unread=bool(initial_message.strip()),
        last_message_at=datetime.utcnow() if initial_message.strip() else None,
    )
    db.add(conversation)
    db.flush()

    if initial_message.strip():
        create_message(db, conversation, "cliente", initial_message.strip())
    else:
        db.commit()

    return RedirectResponse(f"/agent/conversations/{conversation.id}", status_code=303)


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: int,
    text: str = Form(""),
    is_internal: bool = Form(False),
    scheduled_for: str = Form(""),
    attachment: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = get_workspace_conversation(db, current_user, conversation_id)
    if not conversation:
        return RedirectResponse("/agent?error=Conversa+nao+encontrada.", status_code=303)

    message_text = text.strip()
    upload = None
    if attachment and attachment.filename:
        try:
            upload = validate_and_store_upload(attachment, get_settings().max_upload_size_mb, Path("app/static/uploads"))
        except ValueError as exc:
            return RedirectResponse(f"/agent/conversations/{conversation_id}?error={str(exc).replace(' ', '+')}", status_code=303)

    if not message_text and not upload:
        return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)

    try:
        scheduled_at = datetime.fromisoformat(scheduled_for) if scheduled_for else None
    except ValueError:
        return RedirectResponse(f"/agent/conversations/{conversation_id}?error=Data+de+agendamento+invalida.", status_code=303)
    if scheduled_at and scheduled_at <= datetime.utcnow():
        return RedirectResponse(f"/agent/conversations/{conversation_id}?error=Agendamento+deve+ser+futuro.", status_code=303)

    sender = "sistema" if is_internal else "atendente"
    message = create_message(
        db,
        conversation,
        sender,
        message_text,
        is_internal=is_internal,
        scheduled_for=scheduled_at,
        author_user_id=current_user.id,
        attachment_original_name=upload.original_name if upload else None,
        attachment_stored_name=upload.stored_name if upload else None,
        attachment_mime_type=upload.mime_type if upload else None,
        attachment_size_bytes=upload.size_bytes if upload else None,
    )
    if is_internal:
        create_mention_notifications(db, conversation, message, current_user.id)
    return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)


@router.post("/notifications/{notification_id}/read")
def read_mention_notification(notification_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    notification = (
        db.query(MentionNotification)
        .filter(
            MentionNotification.id == notification_id,
            MentionNotification.workspace_id == current_user.workspace_id,
            MentionNotification.mentioned_user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        return RedirectResponse("/agent", status_code=303)
    notification.is_read = True
    db.commit()
    return RedirectResponse(f"/agent/conversations/{notification.conversation_id}", status_code=303)


@router.post("/conversations/{conversation_id}/status")
def update_conversation_status(
    conversation_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = get_workspace_conversation(db, current_user, conversation_id)
    if not conversation or status not in VALID_STATUSES:
        return RedirectResponse(f"/agent/conversations/{conversation_id}?error=Status+invalido.", status_code=303)
    now = datetime.utcnow()
    conversation.status = status
    if status == "finalizada":
        conversation.closed_at = now
        conversation.duration_minutes = int((now - conversation.created_at).total_seconds() // 60)
    else:
        conversation.closed_at = None
        conversation.duration_minutes = None
    db.commit()
    return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)


@router.post("/conversations/{conversation_id}/favorite")
def toggle_favorite(conversation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversation = get_workspace_conversation(db, current_user, conversation_id)
    if conversation:
        conversation.is_favorite = not conversation.is_favorite
        db.commit()
    return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)


@router.post("/conversations/{conversation_id}/transfer")
def transfer_conversation(
    conversation_id: int,
    agent_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = get_workspace_conversation(db, current_user, conversation_id)
    target = get_workspace_user(db, current_user, agent_id)
    if not conversation or not target or not target.is_active or target.role != "agent":
        return RedirectResponse(f"/agent/conversations/{conversation_id}?error=Atendente+invalido+para+transferencia.", status_code=303)
    conversation.agent_id = target.id
    create_message(
        db,
        conversation,
        "sistema",
        f"{current_user.name} transferiu o atendimento para {target.name}.",
        is_internal=True,
        author_user_id=current_user.id,
    )
    return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)


@router.post("/conversations/{conversation_id}/client")
def update_client(
    conversation_id: int,
    full_name: str = Form(...),
    preferred_name: str = Form(""),
    birth_date: str = Form(""),
    gender: str = Form(""),
    phone: str = Form(""),
    phone_country_code: str = Form(""),
    phone_area_code: str = Form(""),
    phone_number: str = Form(""),
    email: str = Form(""),
    cpf: str = Form(""),
    rg: str = Form(""),
    address: str = Form(""),
    zip_code: str = Form(""),
    address_number: str = Form(""),
    address_complement: str = Form(""),
    reference_point: str = Form(""),
    fixed_location: str = Form(""),
    notes: str = Form(""),
    restrictions: str = Form(""),
    complaints: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = get_workspace_conversation(db, current_user, conversation_id)
    if conversation:
        client = conversation.client
        upsert_client_fields(
            client,
            full_name,
            phone,
            email,
            address,
            notes,
            preferred_name=preferred_name,
            birth_date=birth_date,
            gender=gender,
            cpf=cpf,
            rg=rg,
            zip_code=zip_code,
            address_number=address_number,
            address_complement=address_complement,
            reference_point=reference_point,
            fixed_location=fixed_location,
            restrictions=restrictions,
            complaints=complaints,
            phone_country_code=phone_country_code,
            phone_area_code=phone_area_code,
            phone_number=phone_number,
        )
        db.commit()
    return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)


@router.post("/quick-replies")
def create_personal_quick_reply(
    title: str = Form(...),
    shortcut: str = Form(...),
    content: str = Form(...),
    conversation_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not title.strip() or not content.strip():
        return RedirectResponse(f"/agent/conversations/{conversation_id}?error=Resposta+rapida+invalida.", status_code=303)
    db.add(
        QuickReply(
            workspace_id=current_user.workspace_id,
            title=title.strip(),
            shortcut=normalize_shortcut(shortcut),
            content=content.strip(),
            type="pessoal",
            owner_id=current_user.id,
        )
    )
    db.commit()
    return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)
