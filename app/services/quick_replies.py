from app.models.client import Client
from app.models.user import User


TEMPLATE_VARIABLES = [
    ("[nome_preferencial]", "Nome preferencial do cliente"),
    ("[primeiro_nome]", "Primeiro nome do cliente"),
    ("[nome_completo]", "Nome completo do cliente"),
    ("[atendente]", "Nome do atendente logado"),
    ("[telefone]", "Telefone completo com pais e DDD"),
    ("[telefone_numero]", "Somente o numero apos o DDD"),
    ("[codigo_pais]", "Codigo do pais do telefone"),
    ("[ddd]", "DDD do telefone"),
    ("[email]", "E-mail do cliente"),
    ("[data_nascimento]", "Data de nascimento"),
    ("[cpf]", "CPF"),
    ("[rg]", "RG"),
    ("[endereco]", "Endereco do cliente"),
    ("[cep]", "CEP"),
    ("[numero_endereco]", "Numero do endereco"),
    ("[complemento]", "Complemento do endereco"),
    ("[ponto_referencia]", "Ponto de referencia"),
    ("[localizacao_fixa]", "Localizacao fixa"),
    ("[observacoes]", "Observacoes do cadastro"),
    ("[restricoes]", "Restricoes do cliente"),
    ("[reclamacoes]", "Reclamacoes registradas"),
]


def normalize_shortcut(shortcut: str) -> str:
    value = shortcut.strip().lower()
    return value if value.startswith("/") else f"/{value}"


def render_template(content: str, client: Client, attendant: User | None = None) -> str:
    values = {
        "nome_preferencial": client.preferred_name or client.first_name,
        "primeiro_nome": client.first_name,
        "nome_completo": client.full_name,
        "atendente": attendant.name if attendant else "",
        "telefone": client.phone or "",
        "telefone_numero": client.phone_number or "",
        "codigo_pais": client.phone_country_code or "",
        "ddd": client.phone_area_code or "",
        "email": client.email or "",
        "data_nascimento": client.birth_date or "",
        "cpf": client.cpf or "",
        "rg": client.rg or "",
        "endereco": client.address or "",
        "cep": client.zip_code or "",
        "numero_endereco": client.address_number or "",
        "complemento": client.address_complement or "",
        "ponto_referencia": client.reference_point or "",
        "localizacao_fixa": client.fixed_location or "",
        "observacoes": client.notes or "",
        "restricoes": client.restrictions or "",
        "reclamacoes": client.complaints or "",
    }
    rendered = content
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
        rendered = rendered.replace("[" + key + "]", value)
    return rendered
