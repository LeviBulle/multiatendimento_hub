import re

from app.models.client import Client
from app.models.user import User
from app.models.whatsapp_template import WhatsAppTemplate

ALLOWED_TEMPLATE_VARIABLES = {
    "cliente_nome",
    "cliente_telefone",
    "atendente_nome",
}
VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def slugify_template_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "modelo"


def extract_variables(content: str) -> set[str]:
    return set(VARIABLE_PATTERN.findall(content or ""))


def validate_template_variables(content: str) -> None:
    invalid = extract_variables(content) - ALLOWED_TEMPLATE_VARIABLES
    if invalid:
        raise ValueError(f"Variavel de modelo nao permitida: {', '.join(sorted(invalid))}.")


def render_whatsapp_template(template: WhatsAppTemplate, client: Client, user: User) -> str:
    validate_template_variables(template.content)
    values = {
        "cliente_nome": client.preferred_name or client.full_name,
        "cliente_telefone": client.phone or "",
        "atendente_nome": user.name,
    }
    missing = [name for name in extract_variables(template.content) if not values.get(name)]
    if missing:
        raise ValueError(f"Variavel sem valor: {', '.join(sorted(missing))}.")

    def replace(match: re.Match) -> str:
        return values[match.group(1)]

    return VARIABLE_PATTERN.sub(replace, template.content)


def template_preview(template: WhatsAppTemplate, client: Client | None, user: User) -> str:
    if client is None:
        return template.content
    try:
        return render_whatsapp_template(template, client, user)
    except ValueError:
        return template.content
