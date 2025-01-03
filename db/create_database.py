from db.database import Base, engine
from models.models import TicketStock


def create_tables():
    Base.metadata.create_all(bind=engine)
    TicketStock.metadata.create_all(bind=engine)