from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import Category
from schemas import CategoryCreate
import auth_crud

def get_category(db: Session, category_id: int):
    return db.query(Category).filter(Category.id == category_id).first()

def get_categories_by_organization(db: Session, organization_id: int, skip: int = 0, limit: int = 100):
    return db.query(Category).filter(Category.organization_id == organization_id).offset(skip).limit(limit).all()

def get_all_categories(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Category).offset(skip).limit(limit).all()

def create_category(db: Session, category: CategoryCreate):
    # Check if organization exists
    organization = auth_crud.get_organization(db, category.organization_id)
    if not organization:
        raise HTTPException(status_code=400, detail=f"Organization with ID {category.organization_id} does not exist")
    
    db_category = Category(
        name=category.name,
        description=category.description,
        organization_id=category.organization_id
    )
    
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def update_category(db: Session, category_id: int, category_data: CategoryCreate):
    db_category = get_category(db, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Check if organization exists
    organization = auth_crud.get_organization(db, category_data.organization_id)
    if not organization:
        raise HTTPException(status_code=400, detail=f"Organization with ID {category_data.organization_id} does not exist")
    
    db_category.name = category_data.name
    db_category.description = category_data.description
    db_category.organization_id = category_data.organization_id
    
    db.commit()
    db.refresh(db_category)
    return db_category

def delete_category(db: Session, category_id: int):
    db_category = get_category(db, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    db.delete(db_category)
    db.commit()
    return {"message": f"Category {category_id} deleted successfully"}
