from sqlalchemy.orm import Session
from datetime import datetime
from auth_models import User, RefreshToken, get_password_hash
from auth_schemas import UserCreate, RefreshTokenCreate
from models import Organization, Product
from schemas import OrganizationCreate, ProductCreate
from fastapi import HTTPException

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user: UserCreate):
    first_user = db.query(User).first() is None
    
    is_admin = True if first_user else user.is_admin
    
    if get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        organization_id=None,  
        is_admin=is_admin
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


def get_organization(db: Session, organization_id: int):
    return db.query(Organization).filter(Organization.id == organization_id).first()


def get_organization_by_name(db: Session, name: str):
    return db.query(Organization).filter(Organization.name == name).first()


def create_organization(db: Session, organization: OrganizationCreate):
    if get_organization_by_name(db, organization.name):
        raise HTTPException(status_code=400, detail="Organization name already exists")
        
    db_organization = Organization(
        name=organization.name,
        description=organization.description
    )
    db.add(db_organization)
    db.commit()
    db.refresh(db_organization)
    return db_organization


def get_organizations(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Organization).offset(skip).limit(limit).all()


def get_product(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()


def get_products_by_organization(db: Session, organization_id: int, skip: int = 0, limit: int = 100):
    return db.query(Product).filter(Product.organization_id == organization_id).offset(skip).limit(limit).all()


def create_product(db: Session, product: ProductCreate):
    organization = get_organization(db, product.organization_id)
    if not organization:
        raise HTTPException(status_code=400, detail=f"Organization with ID {product.organization_id} does not exist")
        
    db_product = Product(
        name=product.name,
        organization_id=product.organization_id,
        price=product.price,
        label_for_ai=product.label_for_ai
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


def update_product(db: Session, product_id: int, product_data: ProductCreate):
    db_product = get_product(db, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    organization = get_organization(db, product_data.organization_id)
    if not organization:
        raise HTTPException(status_code=400, detail=f"Organization with ID {product_data.organization_id} does not exist")
    
    db_product.name = product_data.name
    db_product.organization_id = product_data.organization_id
    db_product.price = product_data.price
    db_product.label_for_ai = product_data.label_for_ai
    
    db.commit()
    db.refresh(db_product)
    return db_product


def delete_product(db: Session, product_id: int):
    db_product = get_product(db, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db.delete(db_product)
    db.commit()
    return {"message": f"Product {product_id} deleted successfully"}


def update_user_organization(db: Session, user_id: int, organization_id: int):
    db_user = get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_organization = get_organization(db, organization_id)
    if not db_organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    db_user.organization_id = organization_id
    db.commit()
    db.refresh(db_user)
    return db_user
