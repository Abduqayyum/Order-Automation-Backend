from sqlalchemy.orm import Session
from datetime import datetime
from auth_models import User, RefreshToken, get_password_hash
from auth_schemas import UserCreate, RefreshTokenCreate
from fastapi import HTTPException

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user: UserCreate):
    if get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(User).offset(skip).limit(limit).all()

def create_refresh_token_db(db: Session, refresh_token: RefreshTokenCreate):
    db_refresh_token = RefreshToken(
        token=refresh_token.token,
        expires_at=refresh_token.expires_at,
        user_id=refresh_token.user_id,
        revoked=refresh_token.revoked
    )
    db.add(db_refresh_token)
    db.commit()
    db.refresh(db_refresh_token)
    return db_refresh_token

def get_refresh_token_by_token(db: Session, token: str):
    return db.query(RefreshToken).filter(RefreshToken.token == token).first()

def get_user_refresh_tokens(db: Session, user_id: int):
    return db.query(RefreshToken).filter(RefreshToken.user_id == user_id).all()

def revoke_refresh_token_db(db: Session, token: str):
    db_token = get_refresh_token_by_token(db, token)
    if db_token:
        db_token.revoked = True
        db.commit()
        return True
    return False

def revoke_all_user_refresh_tokens(db: Session, user_id: int):
    tokens = get_user_refresh_tokens(db, user_id)
    for token in tokens:
        token.revoked = True
    db.commit()
    return True

def clean_expired_tokens(db: Session):
    now = datetime.utcnow()
    db.query(RefreshToken).filter(RefreshToken.expires_at < now).delete()
    db.commit()
