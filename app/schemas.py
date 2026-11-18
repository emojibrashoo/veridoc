from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import UserType, VerificationResult


class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=50)
    id_number: str | None = Field(default=None, max_length=100)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    name: str
    email: EmailStr
    phone: str | None
    id_number: str | None
    user_type: UserType
    status: str
    created_at: datetime


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class VerificationResponse(BaseModel):
    verification_id: int
    result: VerificationResult
    confidence_score: float
    extracted_text: str
    blockchain_hash: str
    qr_code_data: str | None = None
