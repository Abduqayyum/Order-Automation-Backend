from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    total_price = Column(Float, default=0.0)
    items = relationship("OrderItem", back_populates="order")
    
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
    size = Column(String)
    price = Column(Float)
    
    order = relationship("Order", back_populates="items")
    
    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "quantity": self.quantity,
            "size": self.size,
            "price": self.price
        }
