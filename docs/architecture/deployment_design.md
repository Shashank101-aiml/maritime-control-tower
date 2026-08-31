````markdown
# Deployment Design

This document describes deployment considerations for the Maritime Agentic Control System backend. It covers runtime environment, configuration, database deployment, optional vector store setup, and operational requirements.

## Overview

The Maritime Agentic Control System is a FastAPI backend designed to run in cloud or on-premises environments. Deployment should support:
- secure secret management
- persistent database storage
- optional vector store persistence
- logging and health monitoring
- easier local development and production parity

## Deployment Targets

- Local development
  - SQLite database
  - optional ChromaDB local persistence
- Production
  - PostgreSQL database
  - optional ChromaDB on persistent volume
  - containerized deployment with Docker / Kubernetes

## Architecture

The backend consists of:
- FastAPI application entrypoint
- SQLAlchemy ORM models and database session management
- OAuth2 bearer authentication
- service layer for events, risks, routes, recommendations, notifications
- workflow layer for mission state and route assessments
- optional vectorstore integration via ChromaDB + OpenAI embeddings

## Runtime Requirements

- Python 3.11+
- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `pydantic`
- `python-jose`
- `chromadb` (optional)
- `openai` (optional)
- `pytest` for testing

## Environment Configuration

Use environment variables, ideally loaded from a secure `.env` file or secret manager:

- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `DATABASE_URL`
- `FIRST_SUPERUSER_EMAIL`
- `FIRST_SUPERUSER_PASSWORD`
- `OPENAI_API_KEY` (optional)

Example development config:
```text
SECRET_KEY=change-this-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=sqlite:///./sql_app.db
FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=admin
```

Example production config:
```text
SECRET_KEY=<strong-secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=postgresql://user:password@db-host:5432/maritime
FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=<secure-password>
OPENAI_API_KEY=<openai-key>
```

## Database Deployment

### Local development
- Use SQLite for fast setup
- File path: `./sql_app.db`

### Production
- Use PostgreSQL or another supported relational database
- Ensure `DATABASE_URL` points to the production database
- Provide persistent storage and backups
- Create database user with least privileges

## Vector Store Deployment

The project supports an optional ChromaDB vector store:
- configured with `persist_directory` for local persistence
- suitable for embedding-based retrieval
- ensure the persistence directory is mounted on a persistent volume in production
- if using OpenAI embeddings, set `OPENAI_API_KEY`

## Containerization

Recommended Docker pattern:
- Build a container image with the backend code
- Install required Python dependencies
- Set `WORKDIR` to `/app`
- Expose port `8000`
- Use `uvicorn app.main:app --host 0.0.0.0 --port 8000`

### Deployment considerations
- Use environment variables to configure secrets and database URLs
- Mount persistent volumes for database and vector store data
- Use readiness/liveness probes for health endpoint `/health`
- Route external requests through a reverse proxy or ingress

## Kubernetes / Orchestration

In production:
- Run the app in a Deployment or similar workload resource
- Use ConfigMaps or Secrets for environment variables
- Use a Service to expose the app internally
- Use Ingress for external traffic
- Add health checks for `/health`
- Attach persistent volumes for database and optional ChromaDB persistence

## Logging and Monitoring

- Configure structured console logging
- Ensure logs are captured by the hosting environment
- Monitor:
  - application availability
  - database connection health
  - authentication errors
  - event and workflow processing

## Security

- Do not commit secrets to source control
- Use secure secret storage for production config
- Use HTTPS for all external traffic
- Limit database access to required hosts and services
- Rotate secrets and API keys regularly

## Operational Notes

- Initialize database schema before first startup:
  - run initialization or migration script
- Validate environment variables on startup
- Ensure CORS is configured for frontend integration
- Test authentication and API routes after deployment

## Summary

The deployment design should enable secure, reliable operation of the Maritime Agentic Control System backend. Local development can use SQLite and optional local vector persistence, while production should use PostgreSQL, managed secrets, and persistent storage for any optional vector store data.# filepath: d:\maritime-control-system\maritime-agentic-control-system\docs\architecture\deployment_design.md

# Deployment Design

This document describes deployment considerations for the Maritime Agentic Control System backend. It covers runtime environment, configuration, database deployment, optional vector store setup, and operational requirements.

## Overview

The Maritime Agentic Control System is a FastAPI backend designed to run in cloud or on-premises environments. Deployment should support:
- secure secret management
- persistent database storage
- optional vector store persistence
- logging and health monitoring
- easier local development and production parity

## Deployment Targets

- Local development
  - SQLite database
  - optional ChromaDB local persistence
- Production
  - PostgreSQL database
  - optional ChromaDB on persistent volume
  - containerized deployment with Docker / Kubernetes

## Architecture

The backend consists of:
- FastAPI application entrypoint
- SQLAlchemy ORM models and database session management
- OAuth2 bearer authentication
- service layer for events, risks, routes, recommendations, notifications
- workflow layer for mission state and route assessments
- optional vectorstore integration via ChromaDB + OpenAI embeddings

## Runtime Requirements

- Python 3.11+
- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `pydantic`
- `python-jose`
- `chromadb` (optional)
- `openai` (optional)
- `pytest` for testing

## Environment Configuration

Use environment variables, ideally loaded from a secure `.env` file or secret manager:

- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `DATABASE_URL`
- `FIRST_SUPERUSER_EMAIL`
- `FIRST_SUPERUSER_PASSWORD`
- `OPENAI_API_KEY` (optional)

Example development config:
```text
SECRET_KEY=change-this-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=sqlite:///./sql_app.db
FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=admin
```

Example production config:
```text
SECRET_KEY=<strong-secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=postgresql://user:password@db-host:5432/maritime
FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=<secure-password>
OPENAI_API_KEY=<openai-key>
```

## Database Deployment

### Local development
- Use SQLite for fast setup
- File path: `./sql_app.db`

### Production
- Use PostgreSQL or another supported relational database
- Ensure `DATABASE_URL` points to the production database
- Provide persistent storage and backups
- Create database user with least privileges

## Vector Store Deployment

The project supports an optional ChromaDB vector store:
- configured with `persist_directory` for local persistence
- suitable for embedding-based retrieval
- ensure the persistence directory is mounted on a persistent volume in production
- if using OpenAI embeddings, set `OPENAI_API_KEY`

## Containerization

Recommended Docker pattern:
- Build a container image with the backend code
- Install required Python dependencies
- Set `WORKDIR` to `/app`
- Expose port `8000`
- Use `uvicorn app.main:app --host 0.0.0.0 --port 8000`

### Deployment considerations
- Use environment variables to configure secrets and database URLs
- Mount persistent volumes for database and vector store data
- Use readiness/liveness probes for health endpoint `/health`
- Route external requests through a reverse proxy or ingress

## Kubernetes / Orchestration

In production:
- Run the app in a Deployment or similar workload resource
- Use ConfigMaps or Secrets for environment variables
- Use a Service to expose the app internally
- Use Ingress for external traffic
- Add health checks for `/health`
- Attach persistent volumes for database and optional ChromaDB persistence

## Logging and Monitoring

- Configure structured console logging
- Ensure logs are captured by the hosting environment
- Monitor:
  - application availability
  - database connection health
  - authentication errors
  - event and workflow processing

## Security

- Do not commit secrets to source control
- Use secure secret storage for production config
- Use HTTPS for all external traffic
- Limit database access to required hosts and services
- Rotate secrets and API keys regularly

## Operational Notes

- Initialize database schema before first startup:
  - run initialization or migration script
- Validate environment variables on startup
- Ensure CORS is configured for frontend integration
- Test authentication and API routes after deployment

## Summary

The deployment design should enables secure, reliable operation of the Maritime Agentic Control System backend. Local development can use SQLite and optional local vector persistence, while production should use PostgreSQL, managed secrets, and persistent storage for any optional vector store data.