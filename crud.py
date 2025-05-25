from sqlalchemy.orm import Session
import models
import schemas
from typing import List

def create_order(db: Session, order: schemas.OrderCreate):
    total_price = order.total_price if order.total_price else 0.0
    
    db_order = models.Order(total_price=total_price)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    if total_price == 0.0:
        for item_data in order.items:
            db_item = models.OrderItem(
                order_id=db_order.id,
                item_id=item_data.item_id,
                quantity=item_data.quantity,
                size=item_data.size,
                price=item_data.price
            )
            db.add(db_item)
            total_price += item_data.price * item_data.quantity
    else:
        for item_data in order.items:
            db_item = models.OrderItem(
                order_id=db_order.id,
                item_id=item_data.item_id,
                quantity=item_data.quantity,
                size=item_data.size,
                price=item_data.price
            )
            db.add(db_item)
    
    if total_price != order.total_price:
        db_order.total_price = total_price
    
    db.commit()
    db.refresh(db_order)
    return db_order

def get_orders(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Order).offset(skip).limit(limit).all()

def get_order(db: Session, order_id: int):
    return db.query(models.Order).filter(models.Order.id == order_id).first()

def update_order(db: Session, order_id: int, order: schemas.OrderCreate):
    db_order = get_order(db, order_id)
    if db_order is None:
        return None
    
    db.query(models.OrderItem).filter(models.OrderItem.order_id == order_id).delete()
    
    total_price = order.total_price if order.total_price else 0.0
    
    if total_price == 0.0:
        for item_data in order.items:
            db_item = models.OrderItem(
                order_id=db_order.id,
                item_id=item_data.item_id,
                quantity=item_data.quantity,
                size=item_data.size,
                price=item_data.price
            )
            db.add(db_item)
            total_price += item_data.price * item_data.quantity
    else:
        for item_data in order.items:
            db_item = models.OrderItem(
                order_id=db_order.id,
                item_id=item_data.item_id,
                quantity=item_data.quantity,
                size=item_data.size,
                price=item_data.price
            )
            db.add(db_item)
    
    db_order.total_price = total_price
    
    db.commit()
    db.refresh(db_order)
    return db_order

def delete_order(db: Session, order_id: int):
    db_order = get_order(db, order_id)
    if db_order is None:
        return False
    
    db.delete(db_order)
    db.commit()
    return True
