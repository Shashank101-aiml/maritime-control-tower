from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.dependencies.database import get_db
from app.agents.coordinator.coordinator_agent import CoordinatorAgent

router = APIRouter()

@router.get("/run-workflow")
def run_workflow(session_id: str = None, db: Session = Depends(get_db)):
    return CoordinatorAgent().run(db=db, session_id=session_id)