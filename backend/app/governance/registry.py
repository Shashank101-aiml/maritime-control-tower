from sqlalchemy.orm import Session
from datetime import datetime
from app.models.governance import AgentIdentity, AgentHealth

def register_agent(db: Session, agent_data: dict):
    agent_id = agent_data["id"]
    agent = db.query(AgentIdentity).filter(AgentIdentity.id == agent_id).first()
    
    if agent:
        for key, value in agent_data.items():
            setattr(agent, key, value)
    else:
        agent = AgentIdentity(**agent_data)
        db.add(agent)
        
    # Also initialize health record
    health = db.query(AgentHealth).filter(AgentHealth.agent_id == agent_id).first()
    if not health:
        health = AgentHealth(agent_id=agent_id, status="HEALTHY")
        db.add(health)
        
    db.commit()
    db.refresh(agent)
    return agent

def get_agent(db: Session, agent_id: str):
    return db.query(AgentIdentity).filter(AgentIdentity.id == agent_id).first()

def get_all_agents(db: Session):
    return db.query(AgentIdentity).all()

def update_agent_status(db: Session, agent_id: str, status: str):
    agent = db.query(AgentIdentity).filter(AgentIdentity.id == agent_id).first()
    if agent:
        agent.status = status
        db.commit()
        db.refresh(agent)
    return agent

def record_heartbeat(db: Session, agent_id: str):
    health = db.query(AgentHealth).filter(AgentHealth.agent_id == agent_id).first()
    if health:
        health.last_heartbeat = datetime.utcnow()
        if health.status == "UNAVAILABLE":
            health.status = "HEALTHY"
        db.commit()
