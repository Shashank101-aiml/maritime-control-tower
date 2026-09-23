````markdown
# Maritime Agentic Control System

A FastAPI backend for maritime event logging, route planning, risk management, and recommendation generation. The service supports OAuth2 authentication, relational database persistence, workflow state tracking, notification dispatch, and optional vector search / embeddings integration.

## Features

- REST API for:
  - events
  - risks
  - workflow
  - dashboard
  - recommendations
  - agents
  - health checks
- OAuth2 bearer token authentication
- SQLAlchemy models for users, events, risks, routes, and recommendations
- SQLite support for local development, PostgreSQL support for production
- Event-driven risk assessment and notification support
- Optional ChromaDB-based vector store and OpenAI embeddings integration
- Modular architecture: API routes, services, workflows, dependencies, and schemas
- Automated tests for core route availability


## Requirements

- Python 3.11+
- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `pydantic`
- `python-jose`
- `python-multipart`
- `pytest`
- `chromadb`
- `openai` (optional)

## Setup

1. Clone the repository:

```bash
git clone <https://github.com/Shashank101-aiml/maritime-control-tower.git>
cd maritime-control-tower/backend
```

2. Create and activate a Python virtual environment:

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create the project's single `.env` in the repo root (`cp .env.example .env`) and fill it in. It holds every setting -- backend, database, external API keys and the frontend's `VITE_*` origin -- and is read by Docker Compose, the backend and Vite:

```text
SECRET_KEY=...
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=sqlite:///./sql_app.db
FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=admin
```

## Database

The application supports SQLite locally and Postgres in production. 
Example SQLite:

```text
DATABASE_URL=sqlite:///./sql_app.db
```

Example PostgreSQL:

```text
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

## Run

Start the FastAPI server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open the API documentation:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

- `/` - root endpoint
- `/health` - health check
- `/api/events`
- `/api/risks`
- `/api/workflow`
- `/api/dashboard`
- `/api/recommendations`
- `/api/agents`

## Testing

Run tests with:

```bash
pytest
```

## Notes

- Keep secrets out of source control and use `.env` or secret management.
- The vector store and embeddings components are optional and require `chromadb` and `openai`.
- Use CORS configuration when integrating UI or external services.

## Project Structure

- `app/api` - API routes and dependencies
- `app/core` - configuration, logging, constants
- `app/database` - SQLAlchemy base, connection, session
- `app/models` - database models
- `app/schemas` - Pydantic request/response schemas
- `app/services` - business logic and utilities
- `app/workflows` - higher-level workflows and state
- `app/vectorstore` - ChromaDB / embeddings integration
- `tests` - automated tests

## License

Architected a governed, 12-agent multi-agent system (ingestion, risk, route optimisation, decision, explanation, anomaly detection, feedback) coordinated through an adaptively-routed pipeline, with a runtime governance engine that gates low-confidence or high-criticality actions behind human approval and logs a full audit trail.

Trained and benchmarked three independent LightGBM models against their own real baselines — a port/vessel congestion classifier (138K+ samples across 3 sources, ROC-AUC 0.82), a shipment-delay classifier (9.2K orders, PR-AUC 0.90 vs. a 0.02 baseline on a ~2% positive rate), and a fuel-consumption regressor (R²=0.95, 83.6% lower MAE than a naive baseline) — plus an unsupervised Isolation Forest anomaly detector over real per-port congestion history.

Built a live digital twin (NetworkX graph of 20 real ports and shipping lanes) with multi-objective route optimisation (cost, delay, risk, emissions) and a what-if scenario simulator for evaluating rerouting under corridor disruption.
Ingested real-time AIS vessel positions over WebSocket, live marine/weather conditions across 8 monitored corridors, and maritime news events (NLP classification + location extraction) into the governed pipeline, closing the loop with human-in-the-loop feedback and per-prediction model explainability (LightGBM feature attribution).

Tech Stack: Python, FastAPI, LightGBM, scikit-learn, NetworkX, PostgreSQL (SQLAlchemy, Alembic), React, Vite, Leaflet, Docker, GitHub Actions
