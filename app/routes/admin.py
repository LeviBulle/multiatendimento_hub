from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import require_admin
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.channel import Channel
from app.models.client import Client
from app.models.quick_reply import QuickReply
from app.models.user import User
from app.models.whatsapp_template import WhatsAppTemplate
from app.services.clients import upsert_client_fields
from app.services.mentions import notification_context
from app.services.metrics import get_admin_metrics
from app.services.quick_replies import TEMPLATE_VARIABLES, normalize_shortcut
from app.services.whatsapp_templates import slugify_template_name, validate_template_variables

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


def clean_email(value: str) -> str:
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise ValueError("Informe um e-mail valido.") from exc


def base_context(db: Session, current_user: User, **values) -> dict:
    context = {"current_user": current_user, "demo_mode": get_settings().demo_mode, **values}
    context.update(notification_context(db, current_user))
    return context


def render_users(request, db, current_user, users, edit_user=None, error="", form=None, status_code=200):
    return templates.TemplateResponse(
        request,
        "admin/users.html",
        base_context(db, current_user, active="users", users=users, edit_user=edit_user, error=error, form=form or {}),
        status_code=status_code,
    )


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        base_context(db, current_user, active="dashboard", metrics=get_admin_metrics(db, current_user.workspace_id)),
    )


@router.get("/users")
def users_page(request: Request, edit: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    users = db.query(User).filter(User.workspace_id == current_user.workspace_id, User.role == "agent").order_by(User.name).all()
    edit_user = (
        db.query(User).filter(User.id == edit, User.workspace_id == current_user.workspace_id, User.role == "agent").first()
        if edit
        else None
    )
    return render_users(request, db, current_user, users, edit_user)


@router.post("/users")
def create_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_active: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    users = db.query(User).filter(User.workspace_id == current_user.workspace_id, User.role == "agent").order_by(User.name).all()
    form = {"name": name, "email": email, "is_active": is_active}
    if not name.strip() or not password:
        return render_users(request, db, current_user, users, error="Nome e senha sao obrigatorios.", form=form, status_code=400)
    try:
        normalized_email = clean_email(email)
    except ValueError as exc:
        return render_users(request, db, current_user, users, error=str(exc), form=form, status_code=400)
    if db.query(User).filter(User.workspace_id == current_user.workspace_id, User.email == normalized_email).first():
        return render_users(request, db, current_user, users, error="Ja existe um atendente com este e-mail.", form=form, status_code=400)
    db.add(
        User(
            workspace_id=current_user.workspace_id,
            name=name.strip(),
            email=normalized_email,
            hashed_password=get_password_hash(password),
            role="agent",
            is_active=is_active,
        )
    )
    db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/users/{user_id}/edit")
def edit_user(
    request: Request,
    user_id: int,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(""),
    is_active: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id, User.workspace_id == current_user.workspace_id, User.role == "agent").first()
    users = db.query(User).filter(User.workspace_id == current_user.workspace_id, User.role == "agent").order_by(User.name).all()
    if not user:
        return RedirectResponse("/admin/users", status_code=303)
    try:
        normalized_email = clean_email(email)
    except ValueError as exc:
        return render_users(request, db, current_user, users, user, str(exc), {"name": name, "email": email}, 400)
    duplicated = (
        db.query(User)
        .filter(User.workspace_id == current_user.workspace_id, User.email == normalized_email, User.id != user.id)
        .first()
    )
    if duplicated:
        return render_users(request, db, current_user, users, user, "Ja existe um atendente com este e-mail.", {"name": name, "email": email}, 400)
    user.name = name.strip()
    user.email = normalized_email
    user.is_active = is_active
    if password:
        user.hashed_password = get_password_hash(password)
    db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/users/{user_id}/toggle")
def toggle_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id, User.workspace_id == current_user.workspace_id, User.role == "agent").first()
    if user:
        user.is_active = not user.is_active
        db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@router.get("/channels")
def channels_page(request: Request, edit: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    channels = db.query(Channel).filter(Channel.workspace_id == current_user.workspace_id).order_by(Channel.type, Channel.name).all()
    edit_channel = db.query(Channel).filter(Channel.id == edit, Channel.workspace_id == current_user.workspace_id).first() if edit else None
    return templates.TemplateResponse(request, "admin/channels.html", base_context(db, current_user, active="channels", channels=channels, edit_channel=edit_channel, error=""))


@router.post("/channels")
def create_channel(name: str = Form(...), type: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if name.strip() and type.strip():
        db.add(Channel(workspace_id=current_user.workspace_id, name=name.strip(), type=type.strip(), is_active=True))
        db.commit()
    return RedirectResponse("/admin/channels", status_code=303)


@router.post("/channels/{channel_id}/edit")
def edit_channel(channel_id: int, name: str = Form(...), type: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.workspace_id == current_user.workspace_id).first()
    if channel and name.strip() and type.strip():
        channel.name = name.strip()
        channel.type = type.strip()
        db.commit()
    return RedirectResponse("/admin/channels", status_code=303)


@router.post("/channels/{channel_id}/toggle")
def toggle_channel(channel_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.workspace_id == current_user.workspace_id).first()
    if channel:
        channel.is_active = not channel.is_active
        db.commit()
    return RedirectResponse("/admin/channels", status_code=303)


@router.get("/clients")
def clients_page(request: Request, edit: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    clients = db.query(Client).filter(Client.workspace_id == current_user.workspace_id).order_by(Client.full_name).all()
    edit_client = db.query(Client).filter(Client.id == edit, Client.workspace_id == current_user.workspace_id).first() if edit else None
    return templates.TemplateResponse(request, "admin/clients.html", base_context(db, current_user, active="clients", clients=clients, edit_client=edit_client, error=""))


def fill_client(client: Client, **values):
    upsert_client_fields(client, **values)


@router.post("/clients")
def create_client(
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
    current_user: User = Depends(require_admin),
):
    if not full_name.strip():
        return RedirectResponse("/admin/clients?error=Nome+obrigatorio.", status_code=303)
    client = Client(full_name="", first_name="", workspace_id=current_user.workspace_id)
    upsert_client_fields(client, full_name, phone, email, address, notes, preferred_name=preferred_name, birth_date=birth_date, gender=gender, cpf=cpf, rg=rg, zip_code=zip_code, address_number=address_number, address_complement=address_complement, reference_point=reference_point, fixed_location=fixed_location, restrictions=restrictions, complaints=complaints, phone_country_code=phone_country_code, phone_area_code=phone_area_code, phone_number=phone_number)
    db.add(client)
    db.commit()
    return RedirectResponse("/admin/clients", status_code=303)


@router.post("/clients/{client_id}/edit")
def edit_client(
    client_id: int,
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
    current_user: User = Depends(require_admin),
):
    client = db.query(Client).filter(Client.id == client_id, Client.workspace_id == current_user.workspace_id).first()
    if client and full_name.strip():
        upsert_client_fields(client, full_name, phone, email, address, notes, preferred_name=preferred_name, birth_date=birth_date, gender=gender, cpf=cpf, rg=rg, zip_code=zip_code, address_number=address_number, address_complement=address_complement, reference_point=reference_point, fixed_location=fixed_location, restrictions=restrictions, complaints=complaints, phone_country_code=phone_country_code, phone_area_code=phone_area_code, phone_number=phone_number)
        db.commit()
    return RedirectResponse("/admin/clients", status_code=303)


@router.get("/quick-replies")
def quick_replies_page(request: Request, edit: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    replies = (
        db.query(QuickReply)
        .filter(QuickReply.workspace_id == current_user.workspace_id, QuickReply.type == "global")
        .order_by(QuickReply.shortcut)
        .all()
    )
    edit_reply = (
        db.query(QuickReply)
        .filter(QuickReply.id == edit, QuickReply.workspace_id == current_user.workspace_id, QuickReply.type == "global")
        .first()
        if edit
        else None
    )
    return templates.TemplateResponse(
        request,
        "admin/quick_replies.html",
        base_context(db, current_user, active="quick", replies=replies, edit_reply=edit_reply, template_variables=TEMPLATE_VARIABLES, error=""),
    )


@router.post("/quick-replies")
def create_quick_reply(title: str = Form(...), shortcut: str = Form(...), content: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if title.strip() and content.strip():
        db.add(QuickReply(workspace_id=current_user.workspace_id, title=title.strip(), shortcut=normalize_shortcut(shortcut), content=content.strip(), type="global"))
        db.commit()
    return RedirectResponse("/admin/quick-replies", status_code=303)


@router.post("/quick-replies/{reply_id}/edit")
def edit_quick_reply(reply_id: int, title: str = Form(...), shortcut: str = Form(...), content: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    reply = db.query(QuickReply).filter(QuickReply.id == reply_id, QuickReply.workspace_id == current_user.workspace_id, QuickReply.type == "global").first()
    if reply and title.strip() and content.strip():
        reply.title = title.strip()
        reply.shortcut = normalize_shortcut(shortcut)
        reply.content = content.strip()
        db.commit()
    return RedirectResponse("/admin/quick-replies", status_code=303)


@router.post("/quick-replies/{reply_id}/delete")
def delete_quick_reply(reply_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    reply = db.query(QuickReply).filter(QuickReply.id == reply_id, QuickReply.workspace_id == current_user.workspace_id, QuickReply.type == "global").first()
    if reply:
        db.delete(reply)
        db.commit()
    return RedirectResponse("/admin/quick-replies", status_code=303)


@router.get("/whatsapp-templates")
def whatsapp_templates_page(request: Request, edit: int | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    items = (
        db.query(WhatsAppTemplate)
        .filter(WhatsAppTemplate.workspace_id == current_user.workspace_id)
        .order_by(WhatsAppTemplate.name)
        .all()
    )
    edit_template = (
        db.query(WhatsAppTemplate)
        .filter(WhatsAppTemplate.id == edit, WhatsAppTemplate.workspace_id == current_user.workspace_id)
        .first()
        if edit
        else None
    )
    return templates.TemplateResponse(
        request,
        "admin/whatsapp_templates.html",
        base_context(db, current_user, active="whatsapp_templates", templates=items, edit_template=edit_template, error=request.query_params.get("error", "")),
    )


@router.post("/whatsapp-templates")
def create_whatsapp_template(
    name: str = Form(...),
    language: str = Form("pt_BR"),
    category: str = Form("utility"),
    content: str = Form(...),
    status: str = Form("draft"),
    external_template_id: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        validate_template_variables(content)
    except ValueError as exc:
        return RedirectResponse(f"/admin/whatsapp-templates?error={str(exc).replace(' ', '+')}", status_code=303)
    if name.strip() and content.strip():
        existing = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.workspace_id == current_user.workspace_id, WhatsAppTemplate.name == name.strip()).first()
        if existing:
            return RedirectResponse("/admin/whatsapp-templates?error=Ja+existe+um+modelo+com+este+nome.", status_code=303)
        db.add(
            WhatsAppTemplate(
                workspace_id=current_user.workspace_id,
                name=name.strip(),
                slug=slugify_template_name(name),
                language=language.strip() or "pt_BR",
                category=category,
                content=content.strip(),
                status=status,
                external_template_id=external_template_id.strip() or None,
            )
        )
        db.commit()
    return RedirectResponse("/admin/whatsapp-templates", status_code=303)


@router.post("/whatsapp-templates/{template_id}/edit")
def edit_whatsapp_template(
    template_id: int,
    name: str = Form(...),
    language: str = Form("pt_BR"),
    category: str = Form("utility"),
    content: str = Form(...),
    status: str = Form("draft"),
    external_template_id: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    item = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id, WhatsAppTemplate.workspace_id == current_user.workspace_id).first()
    if item:
        try:
            validate_template_variables(content)
        except ValueError as exc:
            return RedirectResponse(f"/admin/whatsapp-templates?edit={template_id}&error={str(exc).replace(' ', '+')}", status_code=303)
        item.name = name.strip()
        item.slug = slugify_template_name(name)
        item.language = language.strip() or "pt_BR"
        item.category = category
        item.content = content.strip()
        item.status = status
        item.external_template_id = external_template_id.strip() or None
        db.commit()
    return RedirectResponse("/admin/whatsapp-templates", status_code=303)


@router.post("/whatsapp-templates/{template_id}/pause")
def pause_whatsapp_template(template_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    item = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id, WhatsAppTemplate.workspace_id == current_user.workspace_id).first()
    if item:
        item.status = "paused" if item.status == "approved" else "approved"
        db.commit()
    return RedirectResponse("/admin/whatsapp-templates", status_code=303)
