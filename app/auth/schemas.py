import uuid
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    restaurant_name: str
    whatsapp_number: str
    owner_name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    email: str
    role: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
