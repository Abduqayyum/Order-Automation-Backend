from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import OrganizationPrompt
from schemas import OrganizationPromptCreate, OrganizationPromptUpdate
import auth_crud

def get_organization_prompt(db: Session, prompt_id: int):
    return db.query(OrganizationPrompt).filter(OrganizationPrompt.id == prompt_id).first()

def get_prompt_by_organization(db: Session, organization_id: int):
    return db.query(OrganizationPrompt).filter(OrganizationPrompt.organization_id == organization_id).first()

def get_all_prompts(db: Session, skip: int = 0, limit: int = 100):
    return db.query(OrganizationPrompt).offset(skip).limit(limit).all()

def create_organization_prompt(db: Session, prompt: OrganizationPromptCreate):
    organization = auth_crud.get_organization(db, prompt.organization_id)
    if not organization:
        raise HTTPException(status_code=400, detail=f"Organization with ID {prompt.organization_id} does not exist")
    
    existing_prompt = get_prompt_by_organization(db, prompt.organization_id)
    if existing_prompt:
        raise HTTPException(status_code=400, detail=f"A prompt already exists for organization with ID {prompt.organization_id}")
    
    db_prompt = OrganizationPrompt(
        organization_id=prompt.organization_id,
        prompt_text=prompt.prompt_text
    )
    
    db.add(db_prompt)
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def update_organization_prompt(db: Session, organization_id: int, prompt_data: OrganizationPromptUpdate):
    db_prompt = get_prompt_by_organization(db, organization_id)
    if not db_prompt:
        raise HTTPException(status_code=404, detail=f"No prompt found for organization with ID {organization_id}")
    
    db_prompt.prompt_text = prompt_data.prompt_text
    
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def delete_organization_prompt(db: Session, organization_id: int):
    db_prompt = get_prompt_by_organization(db, organization_id)
    if not db_prompt:
        raise HTTPException(status_code=404, detail=f"No prompt found for organization with ID {organization_id}")
    
    db.delete(db_prompt)
    db.commit()
    return {"message": f"Prompt for organization {organization_id} deleted successfully"}
