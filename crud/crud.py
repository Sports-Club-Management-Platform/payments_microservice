from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.models import UserMapping


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
