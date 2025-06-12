from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    users = relationship("User", back_populates="organization")
    products = relationship("Product", back_populates="organization")
    orders = relationship("Order", back_populates="organization")
    prompts = relationship("OrganizationPrompt", back_populates="organization")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    label_for_ai = Column(String)
    price = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    organization = relationship("Organization", back_populates="products")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "productName": self.name.replace('_', ' ').title(),
            "label_for_ai": self.label_for_ai,
            "price": self.price
        }


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    total_price = Column(Float, default=0.0)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    
    items = relationship("OrderItem", back_populates="order")
    organization = relationship("Organization", back_populates="orders")
    
    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "total_price": self.total_price,
            "items": [item.to_dict() for item in self.items]
        }

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    item_id = Column(Integer, index=True)
    quantity = Column(Integer)
    price = Column(Float)
    
    order = relationship("Order", back_populates="items")
    
    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "quantity": self.quantity,
            "price": self.price
        }

class OrganizationPrompt(Base):
    __tablename__ = "organization_prompts"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), unique=True)
    prompt_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    organization = relationship("Organization", back_populates="prompts")
    
    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "prompt_text": self.prompt_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
