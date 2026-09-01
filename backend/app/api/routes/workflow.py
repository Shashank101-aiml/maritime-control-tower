from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.api.dependencies.database import get_db
from app.agents.coordinator.coordinator_agent import CoordinatorAgent
from app.core.limiter import RATE_LIMIT, limiter

router = APIRouter()

@router.get("/run-workflow")
@limiter.limit(RATE_LIMIT)
def run_workflow(request: Request, session_id: str = None, db: Session = Depends(get_db)):
    return CoordinatorAgent().run(db=db, session_id=session_id)
