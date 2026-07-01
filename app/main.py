from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db.base import Base
from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.models import Channel, Client, Conversation, Message, QuickReply, User
from app.routes import admin, agent, auth


def create_app() -> FastAPI:
    app = FastAPI(title="MultiAtendimento Hub")
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(agent.router)

    @app.on_event("startup")
    def on_startup() -> None:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            init_db(db)
        finally:
            db.close()

    return app


app = create_app()
