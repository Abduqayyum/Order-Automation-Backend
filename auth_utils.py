from datetime import datetime, timedelta
from typing import Optional, Tuple
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from auth_models import User, RefreshToken
from auth_schemas import TokenData
import os
from dotenv import load_dotenv
import secrets

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
REFRESH_TOKEN_EXPIRE_HOURS = os.getenv("REFRESH_TOKEN_EXPIRE_HOURS", 720)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(db: Session, user_id: int) -> Tuple[str, datetime]:
    token = secrets.token_hex(32)
    
    expires_at = datetime.utcnow() + timedelta(hours=REFRESH_TOKEN_EXPIRE_HOURS)
    
    db_refresh_token = RefreshToken(
        token=token,
        expires_at=expires_at,
        user_id=user_id
    )
    
    db.add(db_refresh_token)
    db.commit()
    db.refresh(db_refresh_token)
    
    return token, expires_at

def verify_token(token: str, credentials_exception) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
        return token_data
    except JWTError:
        raise credentials_exception

def get_refresh_token(db: Session, token: str):
    return db.query(RefreshToken).filter(RefreshToken.token == token).first()

def is_valid_refresh_token(db: Session, token: str) -> bool:
    db_token = get_refresh_token(db, token)
    if not db_token:
        return False
    
    if db_token.revoked or db_token.expires_at < datetime.utcnow():
        return False
        
    return True

def revoke_refresh_token(db: Session, token: str) -> bool:
    db_token = get_refresh_token(db, token)
    if not db_token:
        return False
    
    db_token.revoked = True
    db.commit()
    return True

def revoke_all_user_tokens(db: Session, user_id: int) -> bool:
    db_tokens = db.query(RefreshToken).filter(RefreshToken.user_id == user_id).all()
    for token in db_tokens:
        token.revoked = True
    
    db.commit()
    return True

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = verify_token(token, credentials_exception)
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

def get_user_from_refresh_token(db: Session, refresh_token: str) -> Optional[User]:
    db_token = get_refresh_token(db, refresh_token)
    if not db_token or not is_valid_refresh_token(db, refresh_token):
        return None
    
    return db.query(User).filter(User.id == db_token.user_id).first()
