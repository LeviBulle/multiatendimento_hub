from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from urllib.parse import parse_qs

from app.core.config import get_settings
from app.core.security import generate_csrf_token, verify_csrf_token
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.routes import admin, agent, auth


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_runtime()
    app = FastAPI(title="Ellub Chat")
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.middleware("http")
    async def csrf_middleware(request, call_next):
        csrf_token = request.cookies.get("csrf_token") or generate_csrf_token()
        request.state.csrf_token = csrf_token
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            body = await request.body()
            content_type = request.headers.get("content-type", "")
            submitted = request.headers.get("X-CSRF-Token")
            if not submitted and "application/x-www-form-urlencoded" in content_type:
                submitted = (parse_qs(body.decode()).get("csrf_token") or [None])[0]
            if not submitted and b'name="csrf_token"' in body:
                marker = b'name="csrf_token"'
                submitted = body.split(marker, 1)[1].split(b"\r\n\r\n", 1)[1].split(b"\r\n", 1)[0].decode()
            if not verify_csrf_token(request.cookies.get("csrf_token"), submitted):
                return PlainTextResponse("Sessao expirada. Atualize a pagina e tente novamente.", status_code=403)

            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = receive
        response = await call_next(request)
        response.set_cookie(
            "csrf_token",
            csrf_token,
            httponly=False,
            samesite="lax",
            secure=settings.cookie_secure,
            max_age=settings.access_token_expire_minutes * 60,
        )
        return response

    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(agent.router)

    @app.on_event("startup")
    def on_startup() -> None:
        db = SessionLocal()
        try:
            init_db(db)
        finally:
            db.close()

    return app


app = create_app()
