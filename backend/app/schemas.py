from datetime import datetime

from pydantic import BaseModel


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ClientCreate(BaseModel):
    label: str


class ClientUpdate(BaseModel):
    label: str | None = None
    enabled: bool | None = None


class ClientOut(BaseModel):
    id: int
    label: str
    username: str
    sub_uuid: str
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SettingsIn(BaseModel):
    domain: str


class SettingsOut(BaseModel):
    domain: str
