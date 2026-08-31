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

4. Create a `.env` file in `backend/app` or project root with required config:

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

This repository is provided as-is for maritime control system backend development.
````
