from datetime import datetime
from pathlib import Path
from shutil import copyfileobj
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.channel import Channel
from app.models.client import Client
from app.models.conversation import Conversation
from app.models.quick_reply import QuickReply
from app.models.user import User
from app.services.clients import upsert_client_fields
from app.services.messages import create_message, process_scheduled_messages
from app.services.quick_replies import normalize_shortcut, render_template

router = APIRouter(prefix="/agent")
templates = Jinja2Templates(directory="app/templates")


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


def chat_context(
    request: Request,
    db: Session,
    current_user: User,
    conversation_id: int | None = None,
    search: str = "",
    tab: str = "atendimentos",
    agent_ids: list[int] | None = None,
    channel_filter: str = "",
) -> dict:
    process_scheduled_messages(db)
    tabs = {"novo", "atendimentos", "nao_lidos", "encerrados"}
    tab = tab if tab in tabs else "atendimentos"

    agents = db.query(User).filter(User.role == "agent", User.is_active.is_(True)).order_by(User.name).all()
    valid_agent_ids = {agent.id for agent in agents}
    selected_agent_ids = [agent_id for agent_id in (agent_ids or []) if agent_id in valid_agent_ids]
    if current_user.role != "admin" and not selected_agent_ids:
        selected_agent_ids = [current_user.id]

    query = (
        db.query(Conversation)
        .options(joinedload(Conversation.client), joinedload(Conversation.channel), joinedload(Conversation.agent))
    )

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
    if channel_filter:
        query = query.join(Conversation.channel).filter(Channel.type == channel_filter)

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

    count_query = db.query(Conversation)
    if channel_filter:
        count_query = count_query.join(Conversation.channel).filter(Channel.type == channel_filter)
    if search:
        like = f"%{search}%"
        count_query = count_query.join(Conversation.client).filter(
            or_(
                Client.full_name.ilike(like),
                Client.first_name.ilike(like),
                Client.phone.ilike(like),
                Client.email.ilike(like),
            )
        )
    status_counts = {
        "novo": count_query.filter(Conversation.agent_id.is_(None), Conversation.status != "finalizada").count(),
        "atendimentos": apply_agent_filter(count_query).filter(Conversation.status.in_(["aberta", "pendente"])).count(),
        "nao_lidos": apply_agent_filter(count_query).filter(Conversation.unread.is_(True), Conversation.status != "finalizada").count(),
        "encerrados": apply_agent_filter(count_query).filter(Conversation.status == "finalizada").count(),
    }

    conversations = query.order_by(Conversation.last_message_at.desc(), Conversation.created_at.desc()).all()
    for conversation in conversations:
        conversation.time_since_last = human_delta(conversation.last_message_at)
    conversation = db.get(Conversation, conversation_id) if conversation_id else (conversations[0] if conversations else None)
    messages = conversation.messages if conversation else []
    channels = db.query(Channel).filter(Channel.is_active.is_(True)).order_by(Channel.type, Channel.name).all()
    quick_replies = []
    shortcuts = {}
    if conversation:
        replies = (
            db.query(QuickReply)
            .filter(or_(QuickReply.type == "global", QuickReply.owner_id == current_user.id))
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
    if search:
        base_params["q"] = search
    if channel_filter:
        base_params["channel"] = channel_filter

    def build_query(**overrides) -> str:
        params = {**base_params, **overrides}
        params = {key: value for key, value in params.items() if value not in (None, "")}
        return urlencode(params, doseq=True)

    return {
        "request": request,
        "current_user": current_user,
        "conversations": conversations,
        "conversation": conversation,
        "messages": messages,
        "channels": channels,
        "agents": agents,
        "quick_replies": quick_replies,
        "shortcuts": shortcuts,
        "filters": {"search": search, "tab": tab, "agent_ids": selected_agent_ids, "channel": channel_filter},
        "status_options": ["aberta", "pendente", "finalizada"],
        "status_counts": status_counts,
        "tab_urls": {name: f"/agent?{build_query(tab=name)}" for name in tabs},
        "list_query": build_query(),
        "agent_filter_options": agents,
    }


@router.get("")
def agent_home(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        request,
        "agent/chat.html",
        chat_context(
            request,
            db,
            current_user,
            search=request.query_params.get("q", ""),
            tab=request.query_params.get("tab", "atendimentos"),
            agent_ids=parse_int_list(request.query_params.getlist("agent_id")),
            channel_filter=request.query_params.get("channel", ""),
        ),
    )


@router.get("/conversations/{conversation_id}")
def conversation_page(conversation_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversation = db.get(Conversation, conversation_id)
    if conversation:
        conversation.unread = False
        if conversation.agent_id is None and current_user.role == "agent":
            conversation.agent_id = current_user.id
        db.commit()
    return templates.TemplateResponse(
        request,
        "agent/chat.html",
        chat_context(
            request,
            db,
            current_user,
            conversation_id,
            search=request.query_params.get("q", ""),
            tab=request.query_params.get("tab", "atendimentos"),
            agent_ids=parse_int_list(request.query_params.getlist("agent_id")),
            channel_filter=request.query_params.get("channel", ""),
        ),
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
    channel = db.get(Channel, channel_id)
    if not channel or not channel.is_active:
        return RedirectResponse("/agent", status_code=303)

    client = Client(full_name="", first_name="")
    upsert_client_fields(client, full_name, phone, email, "", "")
    db.add(client)
    db.flush()

    owner_id = agent_id if current_user.role == "admin" and agent_id else current_user.id
    conversation = Conversation(
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
    conversation = db.get(Conversation, conversation_id)
    if conversation:
        message_text = text.strip()
        if attachment and attachment.filename:
            uploads_dir = Path("app/static/uploads")
            uploads_dir.mkdir(parents=True, exist_ok=True)
            original_name = Path(attachment.filename).name
            stored_name = f"{uuid4().hex}_{original_name}"
            stored_path = uploads_dir / stored_name
            with stored_path.open("wb") as output:
                copyfileobj(attachment.file, output)
            file_url = f"/static/uploads/{stored_name}"
            attachment_line = f"Anexo: {original_name}\n{file_url}"
            message_text = f"{message_text}\n\n{attachment_line}".strip() if message_text else attachment_line

        if not message_text:
            return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)

        scheduled_at = datetime.fromisoformat(scheduled_for) if scheduled_for else None
        sender = "sistema" if is_internal else "atendente"
        create_message(db, conversation, sender, message_text, is_internal=is_internal, scheduled_for=scheduled_at)
    return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)


@router.post("/conversations/{conversation_id}/status")
def update_conversation_status(
    conversation_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = db.get(Conversation, conversation_id)
    if conversation and status in {"aberta", "pendente", "finalizada"}:
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
    conversation = db.get(Conversation, conversation_id)
    if conversation:
        client = db.get(Client, conversation.client_id)
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
def create_personal_quick_reply(title: str = Form(...), shortcut: str = Form(...), content: str = Form(...), conversation_id: int = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db.add(QuickReply(title=title, shortcut=normalize_shortcut(shortcut), content=content, type="pessoal", owner_id=current_user.id))
    db.commit()
    return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)
