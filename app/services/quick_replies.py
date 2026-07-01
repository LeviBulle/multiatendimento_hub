from app.models.client import Client


def normalize_shortcut(shortcut: str) -> str:
    value = shortcut.strip().lower()
    return value if value.startswith("/") else f"/{value}"


def render_template(content: str, client: Client) -> str:
    values = {
        "primeiro_nome": client.first_name,
        "nome_completo": client.full_name,
        "telefone": client.phone or "",
        "email": client.email or "",
    }
    rendered = content
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered
