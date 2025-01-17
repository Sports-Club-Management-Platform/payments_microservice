import logging
import sys

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.models import TicketStock, UserMapping

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))

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

def create_ticket_stock(db: Session, ticket_id: int, stripe_price_id: str, stock: int):
    db_ticket_stock = TicketStock(ticket_id=ticket_id, stripe_price_id=stripe_price_id, stock=stock)
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
def decrement_stock(db: Session, price_id: str, quantity: int):
    db_ticket_stock = db.query(TicketStock).filter(TicketStock.stripe_price_id == price_id).first()

    if db_ticket_stock is None:
        logger.info(f"Ticket with stripe_price_id {price_id} not found.")
        raise HTTPException(status_code=404, detail="Ticket not found")

    logger.info(f"Decrementing stock by {quantity}: {db_ticket_stock.__dict__}")
    db_ticket_stock.stock -= quantity

    if db_ticket_stock.stock < 0:
        logger.info(f"Couldn't decrement stock by {quantity}. Not enough stock.")
        raise HTTPException(status_code=400, detail="Not enough stock")

    db.commit()
    db.refresh(db_ticket_stock)
    logger.info(f"Stock decremented by {quantity}: {db_ticket_stock.__dict__}")
    return db_ticket_stock

def increment_stock(db: Session, price_id: str, quantity: int):
    db_ticket_stock = db.query(TicketStock).filter(TicketStock.stripe_price_id == price_id).first()

    if db_ticket_stock is None:
        logger.info(f"Ticket with stripe_price_id {price_id} not found.")
        raise HTTPException(status_code=404, detail="Ticket not found")

    logger.info(f"Incrementing stock by {quantity}: {db_ticket_stock.__dict__}")
    db_ticket_stock.stock += quantity

    db.commit()
    db.refresh(db_ticket_stock)
    logger.info(f"Stock incremented by {quantity}: {db_ticket_stock.__dict__}")
    return db_ticket_stock

def get_stock_by_ticket_id(db: Session, ticket_id: int):
    db_ticket_stock = db.query(TicketStock).filter(TicketStock.ticket_id == ticket_id).first()
    if db_ticket_stock is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"stock": db_ticket_stock.stock}

def get_stock_by_price_id(db: Session, price_id: str):
    db_ticket_stock = db.query(TicketStock).filter(TicketStock.stripe_price_id == price_id).first()
    if db_ticket_stock is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"stock": db_ticket_stock.stock}

def get_stock_ticket_id_by_price_id(db:Session, price_id: str):
    db_ticket_stock = db.query(TicketStock).filter(TicketStock.stripe_price_id == price_id).first()
    if db_ticket_stock is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return db_ticket_stock.ticket_id
