from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.route import Route
from app.schemas.route import RouteCreate, RouteUpdate


def get_route(db: Session, route_id: int) -> Optional[Route]:
    return db.query(Route).filter(Route.id == route_id).first()


def get_routes(db: Session, skip: int = 0, limit: int = 100) -> List[Route]:
    return db.query(Route).offset(skip).limit(limit).all()


def create_route(db: Session, route_in: RouteCreate) -> Route:
    route = Route(**route_in.dict())
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


def update_route(db: Session, db_route: Route, route_in: RouteUpdate) -> Route:
    update_data = route_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_route, field, value)
    db.add(db_route)
    db.commit()
    db.refresh(db_route)
    return db_route


def delete_route(db: Session, db_route: Route) -> Route:
    db.delete(db_route)
    db.commit()
    return db_route
