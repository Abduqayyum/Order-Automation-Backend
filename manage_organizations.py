import argparse
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
import auth_models
import auth_crud

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

def list_organizations(db: Session):
    organizations = db.query(models.Organization).all()
    if not organizations:
        print("No organizations found.")
        return
    
    print("\nOrganizations:")
    print("ID | Name | Description")
    print("-" * 50)
    for org in organizations:
        print(f"{org.id} | {org.name} | {org.description}")

def list_users(db: Session):
    users = db.query(auth_models.User).all()
    if not users:
        print("No users found.")
        return
    
    print("\nUsers:")
    print("ID | Username | Email | Organization ID | Admin")
    print("-" * 70)
    for user in users:
        print(f"{user.id} | {user.username} | {user.email} | {user.organization_id or 'None'} | {user.is_admin}")

def create_organization(db: Session, name: str, description: str = None):
    existing = db.query(models.Organization).filter(models.Organization.name == name).first()
    if existing:
        print(f"Organization with name '{name}' already exists (ID: {existing.id}).")
        return
    
    org = models.Organization(name=name, description=description)
    db.add(org)
    db.commit()
    db.refresh(org)
    print(f"Created organization: {org.name} (ID: {org.id})")
    return org

def assign_user_to_organization(db: Session, user_id: int, organization_id: int):
    user = db.query(auth_models.User).filter(auth_models.User.id == user_id).first()
    if not user:
        print(f"User with ID {user_id} not found.")
        return
    
    org = db.query(models.Organization).filter(models.Organization.id == organization_id).first()
    if not org:
        print(f"Organization with ID {organization_id} not found.")
        return
    
    user.organization_id = organization_id
    db.commit()
    db.refresh(user)
    print(f"User '{user.username}' (ID: {user.id}) assigned to organization '{org.name}' (ID: {org.id})")

def remove_user_from_organization(db: Session, user_id: int):
    user = db.query(auth_models.User).filter(auth_models.User.id == user_id).first()
    if not user:
        print(f"User with ID {user_id} not found.")
        return
    
    if user.organization_id is None:
        print(f"User '{user.username}' is not assigned to any organization.")
        return
    
    old_org_id = user.organization_id
    user.organization_id = None
    db.commit()
    db.refresh(user)
    print(f"User '{user.username}' (ID: {user.id}) removed from organization (ID: {old_org_id})")

def main():
    parser = argparse.ArgumentParser(description="Manage organizations and user assignments")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    list_orgs_parser = subparsers.add_parser("list-orgs", help="List all organizations")
    
    list_users_parser = subparsers.add_parser("list-users", help="List all users")
    
    create_org_parser = subparsers.add_parser("create-org", help="Create a new organization")
    create_org_parser.add_argument("name", help="Organization name")
    create_org_parser.add_argument("--description", help="Organization description")
    
    assign_parser = subparsers.add_parser("assign", help="Assign a user to an organization")
    assign_parser.add_argument("user_id", type=int, help="User ID")
    assign_parser.add_argument("organization_id", type=int, help="Organization ID")
    
    remove_parser = subparsers.add_parser("remove", help="Remove a user from their organization")
    remove_parser.add_argument("user_id", type=int, help="User ID")
    
    args = parser.parse_args()
    db = get_db()
    
    if args.command == "list-orgs":
        list_organizations(db)
    elif args.command == "list-users":
        list_users(db)
    elif args.command == "create-org":
        create_organization(db, args.name, args.description)
    elif args.command == "assign":
        assign_user_to_organization(db, args.user_id, args.organization_id)
    elif args.command == "remove":
        remove_user_from_organization(db, args.user_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
