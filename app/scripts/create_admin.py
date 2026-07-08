from getpass import getpass
import re

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User
from app.models.workspace import Workspace


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "workspace"


def main() -> None:
    workspace_name = input("Nome do workspace: ").strip()
    name = input("Nome do admin: ").strip()
    email = input("E-mail do admin: ").strip().lower()
    password = getpass("Senha: ")
    confirmation = getpass("Confirme a senha: ")
    if not workspace_name or not name or not email or not password:
        raise SystemExit("Todos os campos sao obrigatorios.")
    if password != confirmation:
        raise SystemExit("As senhas nao conferem.")

    db = SessionLocal()
    try:
        slug = slugify(workspace_name)
        workspace = db.query(Workspace).filter(Workspace.slug == slug).first()
        if not workspace:
            workspace = Workspace(name=workspace_name, slug=slug, is_active=True)
            db.add(workspace)
            db.flush()
        if db.query(User).filter(User.email == email).first():
            raise SystemExit("Ja existe um usuario com esse e-mail.")
        db.add(
            User(
                workspace_id=workspace.id,
                name=name,
                email=email,
                hashed_password=get_password_hash(password),
                role="admin",
                is_active=True,
            )
        )
        db.commit()
        print("Admin inicial criado com sucesso.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
