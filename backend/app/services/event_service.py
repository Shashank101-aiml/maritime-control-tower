#Routes should not contain the business logic, so we use services to handle the business logic. This is a service that handles events.
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.event import Event
from app.schemas.event import EventCreate, EventUpdate


def get_event(db: Session, event_id: int) -> Optional[Event]:
    return db.query(Event).filter(Event.id == event_id).first()


def get_events(db: Session, skip: int = 0, limit: int = 100) -> List[Event]:
    return db.query(Event).offset(skip).limit(limit).all()


def create_event(db: Session, event_in: EventCreate) -> Event:
    event = Event(**event_in.dict())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event(db: Session, db_event: Event, event_in: EventUpdate) -> Event:
    update_data = event_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_event, field, value)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def delete_event(db: Session, db_event: Event) -> Event:
    db.delete(db_event)
    db.commit()
    return db_event
