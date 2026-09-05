from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.limiter import limiter

from app.api.routes.events import router as event_router
from app.api.routes.risks import router as risk_router
from app.api.routes.workflow import router as workflow_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.recommendation import router as recommendation_router
from app.api.routes.agents import router as agents_router
from app.api.routes.health import router as health_router
from app.api.routes.governance import router as governance_router
from app.api.routes.vessels import router as vessels_router

from app.agents.ingestion.ais_client import AISStreamCollector
from app.core.config import settings
from app.core.logging import setup_logging

# app/core/logging.py defined this but nothing ever called it, so every
# logger.info/warning in the application was silently dropped.
setup_logging()
from app.api.routes.congestion import router as congestion_router
from app.api.routes.delay import router as delay_router
from app.api.routes.fuel import router as fuel_router
from app.api.routes.twin import router as twin_router
from app.api.routes.route import router as route_optimization_router
from app.api.routes.simulation import router as simulation_router

from app.api.routes.auth import router as auth_router

from app.api.dependencies.auth import get_current_active_user

from app.core.constants import UserRole
from app.core.logging import get_logger
from app.core.security import hash_password
from app.database.base import Base
from app.api.dependencies.database import engine, get_db
from app.models.governance import AgentIdentity, AgentHealth
from app.models.user import User

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Names below are defined further down this module; that's fine —
    # this body only runs once uvicorn starts serving, by which point the
    # whole module (seed_governance_agents, seed_first_superuser,
    # ais_collector) has finished importing.
    seed_governance_agents()
    seed_first_superuser()
    ais_collector.start()  # No-op when AISSTREAM_API_KEY is unset.
    yield
    ais_collector.stop()


app = FastAPI(
    title="Maritime Agentic Control System",
    description="Backend API for Maritime Agentic AI Control & Route Planning",
    lifespan=lifespan,
)

# Rate limiting, keyed on client IP. The Limiter instance lives in
# app.core.limiter so route modules can decorate without importing this
# module back.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Explicit origin allowlist. `allow_origins=["*"]` with
# allow_credentials=True is invalid per the CORS spec and meant any
# website could call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def seed_first_superuser():
    """Creates the initial admin account if the users table is empty.

    Without this there is no way to obtain a token on a fresh database,
    so every protected route would be permanently unreachable.
    """
    db = next(get_db())
    if db.query(User).count() > 0:
        return

    admin = User(
        email=settings.FIRST_SUPERUSER_EMAIL,
        username=settings.FIRST_SUPERUSER_USERNAME,
        full_name="Initial Administrator",
        hashed_password=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
        is_superuser=True,
    )
    db.add(admin)
    db.commit()

    if settings.FIRST_SUPERUSER_PASSWORD == "admin":
        logger.warning(
            "Seeded superuser '%s' with the default password. Change "
            "FIRST_SUPERUSER_PASSWORD before exposing this service.",
            settings.FIRST_SUPERUSER_USERNAME,
        )
    else:
        logger.info("Seeded initial superuser '%s'.", settings.FIRST_SUPERUSER_USERNAME)


def seed_governance_agents():
    # Schema is owned by Alembic now. create_all() only ever creates
    # missing tables — it never alters an existing one — so any model
    # change after the first run was silently ignored.
    # Run `alembic upgrade head` before starting the app.
    db = next(get_db())
    
    agents = [
        {"id": "coordinator-agent", "agent_name": "Coordinator Agent", "agent_type": "ORCHESTRATOR", "version": "v1.0", "risk_level": "MEDIUM", "criticality": "HIGH", "confidence_threshold": 0.8},
        {"id": "ingestion-agent", "agent_name": "Ingestion Agent", "agent_type": "COLLECTOR", "version": "v1.2", "risk_level": "LOW", "criticality": "MEDIUM", "confidence_threshold": 0.5},
        {"id": "risk-agent", "agent_name": "Risk Agent", "agent_type": "ANALYZER", "version": "v2.1", "risk_level": "HIGH", "criticality": "CRITICAL", "confidence_threshold": 0.75},
        {"id": "route-agent", "agent_name": "Route Agent", "agent_type": "PLANNER", "version": "v1.5", "risk_level": "HIGH", "criticality": "CRITICAL", "confidence_threshold": 0.85, "human_approval_required": True},
        {"id": "decision-agent", "agent_name": "Decision Agent", "agent_type": "PLANNER", "version": "v1.0", "risk_level": "HIGH", "criticality": "HIGH", "confidence_threshold": 0.7},
        {"id": "explanation-agent", "agent_name": "Explanation Agent", "agent_type": "COMMUNICATOR", "version": "v1.0", "risk_level": "LOW", "criticality": "LOW", "confidence_threshold": 0.6},
        {"id": "congestion-agent", "agent_name": "Congestion Prediction Agent", "agent_type": "ANALYZER", "version": "v1.0", "risk_level": "MEDIUM", "criticality": "HIGH", "confidence_threshold": 0.7},
        {"id": "delay-agent", "agent_name": "Delay Prediction Agent", "agent_type": "ANALYZER", "version": "v1.0", "risk_level": "MEDIUM", "criticality": "HIGH", "confidence_threshold": 0.7},
        {"id": "fuel-agent", "agent_name": "Fuel Efficiency Agent", "agent_type": "ANALYZER", "version": "v1.0", "risk_level": "LOW", "criticality": "MEDIUM", "confidence_threshold": 0.5},
    ]
    
    for a in agents:
        existing = db.query(AgentIdentity).filter(AgentIdentity.id == a["id"]).first()
        if not existing:
            agent = AgentIdentity(**a)
            db.add(agent)
            db.commit()
            
            health = AgentHealth(agent_id=a["id"], status="HEALTHY")
            db.add(health)
            db.commit()

ais_collector = AISStreamCollector(settings.AISSTREAM_API_KEY)

@app.get("/")
def root():
    return {
        "message": "Maritime Agentic Control System Running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }

# --- Public routes -----------------------------------------------------
# Login must be reachable without a token, and health checks are polled
# by load balancers and the frontend's connectivity indicator.
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(health_router, prefix="/api")

# --- Protected routes --------------------------------------------------
# Applied at the router level so a newly added endpoint is authenticated
# by default rather than needing to remember a per-route dependency.
protected = [Depends(get_current_active_user)]

app.include_router(event_router, prefix="/api", dependencies=protected)
app.include_router(risk_router, prefix="/api", dependencies=protected)
app.include_router(workflow_router, prefix="/api", dependencies=protected)
app.include_router(dashboard_router, prefix="/api", dependencies=protected)
app.include_router(recommendation_router, prefix="/api", dependencies=protected)
app.include_router(agents_router, prefix="/api", dependencies=protected)
app.include_router(vessels_router, prefix="/api", dependencies=protected)
app.include_router(governance_router, prefix="/api/governance", tags=["governance"], dependencies=protected)
app.include_router(congestion_router, prefix="/api", tags=["congestion"], dependencies=protected)
app.include_router(delay_router, prefix="/api", tags=["delay"], dependencies=protected)
app.include_router(fuel_router, prefix="/api", tags=["fuel"], dependencies=protected)
app.include_router(twin_router, prefix="/api", tags=["twin"], dependencies=protected)
app.include_router(route_optimization_router, prefix="/api", tags=["route"], dependencies=protected)
app.include_router(simulation_router, prefix="/api", tags=["simulation"], dependencies=protected)
