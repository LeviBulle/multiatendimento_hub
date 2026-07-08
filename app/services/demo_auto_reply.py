from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.conversation import Conversation
from app.services.messages import create_message

PAPAGAIO_CLIENT_NAME = "Papagaio da Silva"
PAPAGAIO_REPLY_TEXT = "loro quer biscoito"


def is_papagaio_conversation(conversation: Conversation) -> bool:
    client_name = (conversation.client.full_name or "").strip().lower()
    return client_name == PAPAGAIO_CLIENT_NAME.lower()


def create_papagaio_reply(db: Session, conversation: Conversation) -> None:
    if not get_settings().demo_mode:
        return
    if not is_papagaio_conversation(conversation):
        return
    create_message(db, conversation, "cliente", PAPAGAIO_REPLY_TEXT)
