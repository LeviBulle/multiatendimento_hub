import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.NamedTemporaryFile(delete=False, suffix='.db').name}"
os.environ["DEMO_MODE"] = "true"
os.environ["APP_ENV"] = "development"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SECRET_KEY"] = "test-secret"

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.db.base import Base
from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.user import User
from app.models.workspace import Workspace


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def csrf(client: TestClient) -> str:
    client.get("/login")
    return client.cookies.get("csrf_token")


def login(client: TestClient, email: str = "admin@hub.local", password: str = "admin123"):
    token = csrf(client)
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": token},
        follow_redirects=False,
    )


def post_csrf(client: TestClient, url: str, data: dict | None = None, **kwargs):
    payload = dict(data or {})
    payload["csrf_token"] = csrf(client)
    return client.post(url, data=payload, follow_redirects=False, **kwargs)


def create_workspace(db, name: str = "Workspace Teste", slug: str = "workspace-teste") -> Workspace:
    workspace = Workspace(name=name, slug=slug, is_active=True)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def create_admin(db, workspace: Workspace, email: str = "admin-teste@hub.local", password: str = "123456") -> User:
    admin = User(
        workspace_id=workspace.id,
        name="Admin Teste",
        email=email,
        hashed_password=get_password_hash(password),
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
