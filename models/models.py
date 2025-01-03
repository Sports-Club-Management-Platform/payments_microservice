import uuid

from sqlalchemy import Column, Integer, String

from db.database import Base


class UserMapping(Base):
    __tablename__ = "user_mapping"

    uuid: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: str = Column(String(36), nullable=False)

class TicketStock(Base):
    __tablename__ = "ticket_stock"
    ticket_id = Column(Integer, primary_key=True)
    stock = Column(Integer, nullable=False)
