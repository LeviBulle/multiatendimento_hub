from pydantic import BaseModel, EmailStr


class ClientCreate(BaseModel):
    full_name: str
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None
