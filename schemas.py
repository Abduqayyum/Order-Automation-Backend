from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class OrderItemBase(BaseModel):
    item_id: int
    quantity: int
    price: Optional[float] = None  

class OrderItemCreate(OrderItemBase):
    pass

class OrderItem(OrderItemBase):
    id: int
    order_id: int

    class Config:
        orm_mode = True

class OrderBase(BaseModel):
    total_price: Optional[float] = 0.0
    organization_id: Optional[int] = None

class OrderCreate(OrderBase):
    items: List[OrderItemCreate] = []

class Order(OrderBase):
    id: int
    created_at: datetime
    total_price: float
    organization_id: Optional[int] = None
    items: List[OrderItem] = []

    class Config:
        orm_mode = True


class OrganizationBase(BaseModel):
    name: str
    description: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    pass


class Organization(OrganizationBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class ProductBase(BaseModel):
    name: str
    organization_id: int
    price: float
    label_for_ai: str


class ProductCreate(ProductBase):
    pass


class Product(ProductBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class OrganizationPromptBase(BaseModel):
    organization_id: int
    prompt_text: str


class OrganizationPromptCreate(OrganizationPromptBase):
    pass


class OrganizationPromptUpdate(BaseModel):
    prompt_text: str


class OrganizationPrompt(OrganizationPromptBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
