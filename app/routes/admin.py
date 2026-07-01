from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.channel import Channel
from app.models.client import Client
from app.models.quick_reply import QuickReply
from app.models.user import User
from app.services.clients import upsert_client_fields
from app.services.metrics import get_admin_metrics
from app.services.quick_replies import normalize_shortcut

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return templates.TemplateResponse(request, "admin/dashboard.html", {"current_user": current_user, "active": "dashboard", "metrics": get_admin_metrics(db)})


@router.get("/users")
def users_page(request: Request, edit: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    users = db.query(User).filter(User.role == "agent").order_by(User.name).all()
    edit_user = db.get(User, edit) if edit else None
    return templates.TemplateResponse(request, "admin/users.html", {"current_user": current_user, "active": "users", "users": users, "edit_user": edit_user})


@router.post("/users")
def create_user(name: str = Form(...), email: str = Form(...), password: str = Form(...), is_active: bool = Form(True), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = User(name=name, email=email, hashed_password=get_password_hash(password), role="agent", is_active=is_active)
    db.add(user)
    db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/users/{user_id}/edit")
def edit_user(user_id: int, name: str = Form(...), email: str = Form(...), password: str = Form(""), is_active: bool = Form(True), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user and user.role == "agent":
        user.name = name
        user.email = email
        user.is_active = is_active
        if password:
            user.hashed_password = get_password_hash(password)
        db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/users/{user_id}/toggle")
def toggle_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user and user.role == "agent":
        user.is_active = not user.is_active
        db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.get("/channels")
def channels_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    channels = db.query(Channel).order_by(Channel.type, Channel.name).all()
    return templates.TemplateResponse(request, "admin/channels.html", {"current_user": current_user, "active": "channels", "channels": channels})


@router.post("/channels")
def create_channel(name: str = Form(...), type: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    db.add(Channel(name=name, type=type, is_active=True))
    db.commit()
    return RedirectResponse("/admin/channels", status_code=303)


@router.get("/clients")
def clients_page(request: Request, edit: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    clients = db.query(Client).order_by(Client.full_name).all()
    edit_client = db.get(Client, edit) if edit else None
    return templates.TemplateResponse(request, "admin/clients.html", {"current_user": current_user, "active": "clients", "clients": clients, "edit_client": edit_client})


@router.post("/clients")
def create_client(full_name: str = Form(...), phone: str = Form(""), email: str = Form(""), address: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    client = Client(full_name="", first_name="")
    upsert_client_fields(client, full_name, phone, email, address, notes)
    db.add(client)
    db.commit()
    return RedirectResponse("/admin/clients", status_code=303)


@router.post("/clients/{client_id}/edit")
def edit_client(client_id: int, full_name: str = Form(...), phone: str = Form(""), email: str = Form(""), address: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    client = db.get(Client, client_id)
    if client:
        upsert_client_fields(client, full_name, phone, email, address, notes)
        db.commit()
    return RedirectResponse("/admin/clients", status_code=303)


@router.get("/quick-replies")
def quick_replies_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    replies = db.query(QuickReply).filter(QuickReply.type == "global").order_by(QuickReply.shortcut).all()
    return templates.TemplateResponse(request, "admin/quick_replies.html", {"current_user": current_user, "active": "quick", "replies": replies})


@router.post("/quick-replies")
def create_quick_reply(title: str = Form(...), shortcut: str = Form(...), content: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    db.add(QuickReply(title=title, shortcut=normalize_shortcut(shortcut), content=content, type="global"))
    db.commit()
    return RedirectResponse("/admin/quick-replies", status_code=303)
