from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.client import Client
from app.models.conversation import Conversation
from app.models.quick_reply import QuickReply
from app.models.user import User
from app.services.clients import upsert_client_fields
from app.services.messages import create_message, process_scheduled_messages
from app.services.quick_replies import normalize_shortcut, render_template

router = APIRouter(prefix="/agent")
templates = Jinja2Templates(directory="app/templates")


def human_delta(value: datetime | None) -> str:
    if not value:
        return "sem mensagens"
    minutes = int((datetime.utcnow() - value).total_seconds() // 60)
    if minutes < 1:
        return "agora"
    if minutes < 60:
        return f"{minutes}min"
    return f"{minutes // 60}h"


def chat_context(request: Request, db: Session, current_user: User, conversation_id: int | None = None) -> dict:
    process_scheduled_messages(db)
    conversations = (
        db.query(Conversation)
        .options(joinedload(Conversation.client), joinedload(Conversation.channel), joinedload(Conversation.agent))
        .order_by(Conversation.last_message_at.desc(), Conversation.created_at.desc())
        .all()
    )
    for conversation in conversations:
        conversation.time_since_last = human_delta(conversation.last_message_at)
    conversation = db.get(Conversation, conversation_id) if conversation_id else (conversations[0] if conversations else None)
    messages = conversation.messages if conversation else []
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
            rendered = render_template(reply.content, conversation.client)
            quick_replies.append({"shortcut": reply.shortcut, "rendered": rendered})
            shortcuts[reply.shortcut] = rendered
    return {
        "request": request,
        "current_user": current_user,
        "conversations": conversations,
        "conversation": conversation,
        "messages": messages,
        "quick_replies": quick_replies,
        "shortcuts": shortcuts,
    }


@router.get("")
def agent_home(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse(request, "agent/chat.html", chat_context(request, db, current_user))


@router.get("/conversations/{conversation_id}")
def conversation_page(conversation_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversation = db.get(Conversation, conversation_id)
    if conversation:
        conversation.unread = False
        if conversation.agent_id is None and current_user.role == "agent":
            conversation.agent_id = current_user.id
        db.commit()
    return templates.TemplateResponse(request, "agent/chat.html", chat_context(request, db, current_user, conversation_id))


@router.post("/conversations/{conversation_id}/messages")
def send_message(conversation_id: int, text: str = Form(...), is_internal: bool = Form(False), scheduled_for: str = Form(""), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversation = db.get(Conversation, conversation_id)
    if conversation:
        scheduled_at = datetime.fromisoformat(scheduled_for) if scheduled_for else None
        sender = "sistema" if is_internal else "atendente"
        create_message(db, conversation, sender, text, is_internal=is_internal, scheduled_for=scheduled_at)
    return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)


@router.post("/conversations/{conversation_id}/client")
def update_client(conversation_id: int, full_name: str = Form(...), phone: str = Form(""), email: str = Form(""), address: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversation = db.get(Conversation, conversation_id)
    if conversation:
        client = db.get(Client, conversation.client_id)
        upsert_client_fields(client, full_name, phone, email, address, notes)
        db.commit()
    return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)


@router.post("/quick-replies")
def create_personal_quick_reply(title: str = Form(...), shortcut: str = Form(...), content: str = Form(...), conversation_id: int = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db.add(QuickReply(title=title, shortcut=normalize_shortcut(shortcut), content=content, type="pessoal", owner_id=current_user.id))
    db.commit()
    return RedirectResponse(f"/agent/conversations/{conversation_id}", status_code=303)
