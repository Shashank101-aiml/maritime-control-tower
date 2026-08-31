# filepath: requirements.md

# Requirements

## Overview

This document defines the requirements for the Maritime Agentic Control System backend. The project is a FastAPI-based API that supports maritime event logging, risk management, route planning, recommendations, and integration with vector search / embeddings components.

## Functional Requirements

- Provide REST API endpoints for:
  - events
  - risks
  - workflow
  - dashboard
  - recommendations
  - agents
  - health checks
- Authenticate users through OAuth2 bearer token flow
- Store users, events, risks, routes, and recommendations in a relational database
- Support route planning and mission state transition tracking
- Generate risk assessments and recommendations from events and route data
- Send notification alerts for high-severity events
- Support retrieval of semantic documents via vector store integration

## Non-functional Requirements

- Backend framework: FastAPI
- Database persistence:
  - SQLite for local development
  - PostgreSQL for production deployment
- ORM: SQLAlchemy
- Configuration using Pydantic settings and `.env`
- Logging configured for structured console output
- Modular architecture with separate layers for:
  - API routes
  - database dependencies
  - schemas
  - models
  - services
  - workflows
  - vectorstore integration
- Automated tests for API route availability and core components

## Dependencies

- Python 3.11+ (recommended)
- fastapi
- uvicorn
- sqlalchemy
- pydantic
- jose
- python-multipart
- fastapi[all] or equivalent
- pytest
- pytest-cov
- requests
- chromadb
- openai (optional, for embeddings)
- any PostgreSQL driver for production:
  - psycopg[binary] or asyncpg if needed

## Environment Variables

- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `DATABASE_URL`
- `FIRST_SUPERUSER_EMAIL`
- `FIRST_SUPERUSER_PASSWORD`
- `OPENAI_API_KEY` (if using OpenAI embeddings)

## Deployment Requirements

- Persistent storage for the chosen database
- Secure storage of secret keys
- CORS enabled for frontend integration
- Logging available in the hosting environment
- Optional persistence directory for ChromaDB if using vector storage

## Notes

- The backend should be containerizable for consistent deployment.
- The vector store component is optional and should gracefully degrade if not configured.
- Ensure the database schema initializes before API startup.
- Keep credentials out of source control via `.env` or secret management.