import uuid
from db.database import Base
from sqlalchemy import Column, Integer, String


class UserMapping(Base):
    __tablename__ = "user_mapping"

    uuid: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: str = Column(String(36), nullable=False)
