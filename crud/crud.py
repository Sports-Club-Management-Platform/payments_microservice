from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.models import TicketStock, UserMapping


def create_user_mapping(db: Session, user_id: str):
    db_user_mapping = UserMapping(user_id=user_id)
    db.add(db_user_mapping)
    db.commit()
    db.refresh(db_user_mapping)
    return db_user_mapping


def get_user_id(db: Session, uuid):
    return db.query(UserMapping).filter(UserMapping.uuid == uuid).first()


def get_user_mapping_by_uuid( db: Session, uuid):
    db_user_mapping = get_user_id(db, uuid)
    if db_user_mapping is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user_mapping

def create_ticket_stock(db: Session, ticket_id: int, stock: int):
    db_ticket_stock = TicketStock(ticket_id=ticket_id, stock=stock)
    db.add(db_ticket_stock)
    db.commit()
    db.refresh(db_ticket_stock)
    return db_ticket_stock

def update_ticket_stock(db: Session, ticket_id: int, stock: int):
    db_ticket_stock = db.query(TicketStock).filter(TicketStock.ticket_id == ticket_id).first()
    if db_ticket_stock is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    db_ticket_stock.stock = stock
    db.commit()
    db.refresh(db_ticket_stock)
    return db_ticket_stock

# Need to add function to decrement stock and other things
