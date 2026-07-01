from app.models.client import Client


def extract_first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else ""


def upsert_client_fields(client: Client, full_name: str, phone: str | None, email: str | None, address: str | None, notes: str | None) -> Client:
    client.full_name = full_name.strip()
    client.first_name = extract_first_name(full_name)
    client.phone = phone or None
    client.email = email or None
    client.address = address or None
    client.notes = notes or None
    return client
