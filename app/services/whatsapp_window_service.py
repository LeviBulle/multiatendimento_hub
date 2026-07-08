from datetime import datetime, timedelta

from app.core.config import get_settings
from app.core.time import as_utc, utc_now
from app.models.conversation import Conversation

WHATSAPP_WINDOW_ERROR = "A janela de atendimento do WhatsApp expirou. Envie um modelo aprovado e aguarde uma nova mensagem do cliente."


def is_whatsapp_conversation(conversation: Conversation) -> bool:
    return bool(conversation.channel and conversation.channel.type.strip().lower() == "whatsapp")


def get_window_expires_at(conversation: Conversation) -> datetime | None:
    last_customer_message_at = as_utc(conversation.last_customer_message_at)
    if not is_whatsapp_conversation(conversation) or not last_customer_message_at:
        return None
    return last_customer_message_at + timedelta(hours=get_settings().whatsapp_customer_window_hours)


def get_remaining_seconds(conversation: Conversation, now: datetime | None = None) -> int | None:
    expires_at = get_window_expires_at(conversation)
    if not expires_at:
        return None
    current = as_utc(now) or utc_now()
    return max(0, int((expires_at - current).total_seconds()))


def get_window_status(conversation: Conversation, now: datetime | None = None) -> str:
    if not is_whatsapp_conversation(conversation):
        return "not_applicable"
    if not conversation.last_customer_message_at:
        return "waiting_for_customer"
    remaining = get_remaining_seconds(conversation, now)
    if remaining is None or remaining <= 0:
        return "expired"
    settings = get_settings()
    if remaining <= settings.whatsapp_window_urgent_minutes * 60:
        return "urgent"
    if remaining <= settings.whatsapp_window_warning_hours * 60 * 60:
        return "warning"
    return "active"


def is_window_open(conversation: Conversation, now: datetime | None = None) -> bool:
    return get_window_status(conversation, now) in {"active", "warning", "urgent"}


def can_send_freeform_message(conversation: Conversation, now: datetime | None = None) -> bool:
    settings = get_settings()
    if not settings.enable_whatsapp_window_enforcement:
        return True
    if not is_whatsapp_conversation(conversation):
        return True
    return is_window_open(conversation, now)


def refresh_customer_window(conversation: Conversation, customer_message_time: datetime) -> None:
    if not is_whatsapp_conversation(conversation):
        return
    current = as_utc(conversation.last_customer_message_at)
    incoming = as_utc(customer_message_time) or utc_now()
    if current is None or incoming > current:
        conversation.last_customer_message_at = incoming


def format_remaining(seconds: int | None) -> str:
    if seconds is None:
        return ""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}h {minutes:02d}m"


def format_compact_remaining(seconds: int | None) -> str:
    if seconds is None:
        return ""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def format_datetime(value: datetime | None) -> str:
    value = as_utc(value)
    if not value:
        return "-"
    return value.strftime("%d/%m/%Y as %H:%M")


def get_window_display_data(conversation: Conversation, now: datetime | None = None) -> dict:
    status = get_window_status(conversation, now)
    remaining = get_remaining_seconds(conversation, now)
    expires_at = get_window_expires_at(conversation)
    labels = {
        "not_applicable": "",
        "waiting_for_customer": "WhatsApp · aguardando cliente",
        "active": f"WhatsApp · {format_remaining(remaining)}",
        "warning": f"WhatsApp · {format_remaining(remaining)}",
        "urgent": f"WhatsApp · {format_remaining(remaining)}",
        "expired": "WhatsApp · janela fechada",
    }
    tooltip = ""
    if status != "not_applicable":
        tooltip = (
            f"Ultima mensagem do cliente: {format_datetime(conversation.last_customer_message_at)}\n"
            f"Janela expira: {format_datetime(expires_at)}"
        )
    return {
        "status": status,
        "is_applicable": status != "not_applicable",
        "is_open": status in {"active", "warning", "urgent"},
        "remaining_seconds": remaining or 0,
        "expires_at_utc": expires_at.isoformat() if expires_at else "",
        "last_customer_message_at": format_datetime(conversation.last_customer_message_at),
        "expires_at": format_datetime(expires_at),
        "label": labels[status],
        "remaining_label": format_remaining(remaining),
        "compact_label": format_compact_remaining(remaining) if status in {"active", "warning", "urgent"} else ("fechada" if status == "expired" else "aguarda"),
        "tooltip": tooltip,
    }
