from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class RefreshTokenBase(BaseModel):
    token: str
    expires_at: datetime
    revoked: bool = False

class RefreshTokenCreate(RefreshTokenBase):
    user_id: int

class RefreshToken(RefreshTokenBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class User(UserBase):
    id: int
    refresh_tokens: List[RefreshToken] = []

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str
