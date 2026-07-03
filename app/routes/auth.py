from pathlib import Path
from uuid import uuid4

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Form, Request
from fastapi import File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.user import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
AVATAR_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
}


def clean_email(value: str) -> str:
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise ValueError("Informe um e-mail valido.") from exc


def store_avatar(upload: UploadFile) -> str:
    original_name = Path(upload.filename or "").name
    suffix = Path(original_name).suffix.lower()
    mime_type = upload.content_type or "application/octet-stream"
    if suffix not in AVATAR_TYPES or mime_type not in AVATAR_TYPES[suffix]:
        raise ValueError("Foto invalida. Envie JPG, PNG ou WEBP.")
    uploads_dir = Path("app/static/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{suffix}"
    stored_path = uploads_dir / stored_name
    max_bytes = get_settings().max_upload_size_mb * 1024 * 1024
    size = 0
    with stored_path.open("wb") as output:
        while True:
            chunk = upload.file.read(1024 * 512)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                output.close()
                stored_path.unlink(missing_ok=True)
                raise ValueError(f"Foto maior que o limite de {get_settings().max_upload_size_mb} MB.")
            output.write(chunk)
    return stored_name


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None, "demo_mode": get_settings().demo_mode},
    )


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    settings = get_settings()
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if (
        not user
        or not user.is_active
        or not user.workspace
        or not user.workspace.is_active
        or not verify_password(password, user.hashed_password)
    ):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "E-mail ou senha invalidos.", "demo_mode": settings.demo_mode},
            status_code=400,
        )

    token = create_access_token(user.id)
    target = "/admin" if user.role == "admin" else "/agent"
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response


@router.post("/profile/availability")
def update_availability(
    is_available: bool = Form(False),
    next_url: str = Form("/agent"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.is_available = is_available
    db.commit()
    target = next_url if next_url.startswith("/") and not next_url.startswith("//") else "/agent"
    return RedirectResponse(target, status_code=303)


@router.post("/profile")
def update_profile(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(""),
    avatar: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = "/agent" if current_user.role != "admin" else "/admin"
    if not name.strip():
        return RedirectResponse(f"{target}?error=Nome+obrigatorio.", status_code=303)
    try:
        normalized_email = clean_email(email)
    except ValueError as exc:
        return RedirectResponse(f"{target}?error={str(exc).replace(' ', '+')}", status_code=303)
    duplicated = (
        db.query(User)
        .filter(User.workspace_id == current_user.workspace_id, User.email == normalized_email, User.id != current_user.id)
        .first()
    )
    if duplicated:
        return RedirectResponse(f"{target}?error=Ja+existe+um+usuario+com+este+e-mail.", status_code=303)
    current_user.name = name.strip()
    current_user.email = normalized_email
    if password:
        current_user.hashed_password = get_password_hash(password)
    if avatar and avatar.filename:
        try:
            current_user.avatar_stored_name = store_avatar(avatar)
        except ValueError as exc:
            return RedirectResponse(f"{target}?error={str(exc).replace(' ', '+')}", status_code=303)
    db.commit()
    return RedirectResponse(target, status_code=303)


@router.get("/")
def root():
    return RedirectResponse("/login", status_code=303)
