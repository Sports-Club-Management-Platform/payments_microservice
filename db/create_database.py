from db.database import Base, engine


def create_tables():
    Base.metadata.create_all(bind=engine)