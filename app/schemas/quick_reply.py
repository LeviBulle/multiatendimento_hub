from pydantic import BaseModel


class QuickReplyCreate(BaseModel):
    title: str
    shortcut: str
    content: str
    type: str = "global"
