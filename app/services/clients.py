from app.models.client import Client


def only_digits(value: str | None) -> str:
    return "".join(char for char in (value or "") if char.isdigit())


def extract_first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else ""


def format_cpf(value: str | None) -> str | None:
    digits = only_digits(value)[:11]
    if not digits:
        return None
    if len(digits) <= 3:
        return digits
    if len(digits) <= 6:
        return f"{digits[:3]}.{digits[3:]}"
    if len(digits) <= 9:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:]}"
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def format_birth_date(value: str | None) -> str | None:
    digits = only_digits(value)[:8]
    if not digits:
        return None
    if len(digits) <= 2:
        return digits
    if len(digits) <= 4:
        return f"{digits[:2]}/{digits[2:]}"
    return f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"


def format_phone_number(value: str | None) -> str | None:
    digits = only_digits(value)[:9]
    if not digits:
        return None
    if len(digits) <= 4:
        return digits
    if len(digits) <= 8:
        return f"{digits[:4]}-{digits[4:]}"
    return f"{digits[:5]}-{digits[5:]}"


def split_legacy_phone(value: str | None) -> tuple[str | None, str | None, str | None]:
    digits = only_digits(value)
    if not digits:
        return None, None, None
    if len(digits) >= 13:
        return digits[:2], digits[2:4], format_phone_number(digits[4:13])
    if len(digits) >= 12:
        return digits[:2], digits[2:4], format_phone_number(digits[4:12])
    if len(digits) >= 10:
        return "55", digits[:2], format_phone_number(digits[2:])
    return None, None, format_phone_number(digits)


def compose_phone(country_code: str | None, area_code: str | None, number: str | None) -> str | None:
    country = only_digits(country_code)[:3]
    area = only_digits(area_code)[:2]
    formatted_number = format_phone_number(number)
    parts = []
    if country:
        parts.append(f"+{country}")
    if area:
        parts.append(area)
    if formatted_number:
        parts.append(formatted_number)
    return " ".join(parts) or None


def upsert_client_fields(
    client: Client,
    full_name: str,
    phone: str | None,
    email: str | None,
    address: str | None,
    notes: str | None,
    preferred_name: str | None = None,
    birth_date: str | None = None,
    gender: str | None = None,
    cpf: str | None = None,
    rg: str | None = None,
    zip_code: str | None = None,
    address_number: str | None = None,
    address_complement: str | None = None,
    reference_point: str | None = None,
    fixed_location: str | None = None,
    restrictions: str | None = None,
    complaints: str | None = None,
    phone_country_code: str | None = None,
    phone_area_code: str | None = None,
    phone_number: str | None = None,
) -> Client:
    normalized_full_name = full_name.strip().upper()
    legacy_country, legacy_area, legacy_number = split_legacy_phone(phone)
    country = only_digits(phone_country_code)[:3] or legacy_country
    area = only_digits(phone_area_code)[:2] or legacy_area
    number = format_phone_number(phone_number) or legacy_number

    client.full_name = normalized_full_name
    client.first_name = extract_first_name(normalized_full_name)
    client.preferred_name = preferred_name.strip().title() if preferred_name and preferred_name.strip() else None
    client.birth_date = format_birth_date(birth_date)
    client.gender = gender or None
    client.phone_country_code = country
    client.phone_area_code = area
    client.phone_number = number
    client.phone = compose_phone(country, area, number) or (phone.strip() if phone and phone.strip() else None)
    client.email = email or None
    client.cpf = format_cpf(cpf)
    client.rg = rg or None
    client.address = address or None
    client.zip_code = zip_code or None
    client.address_number = address_number or None
    client.address_complement = address_complement or None
    client.reference_point = reference_point or None
    client.fixed_location = fixed_location or None
    client.notes = notes or None
    client.restrictions = restrictions or None
    client.complaints = complaints or None
    return client
