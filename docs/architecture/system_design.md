````markdown
# System Design

This document describes the overall architecture and system design for the Maritime Agentic Control System backend. It covers application layers, key services, data flow, integrations, and component responsibilities.

## Overview

The Maritime Agentic Control System is a modular FastAPI backend that enables maritime event logging, route planning, risk assessment, and recommendation generation. The system is designed to support:
- secure OAuth2 authentication
- relational database persistence
- service-oriented business logic
- workflow orchestration
- optional vector search and embeddings

## Architecture

The system uses a layered architecture with clear separation of concerns:

- API layer
  - FastAPI routes and request handling
  - path operations for events, risks, routes, recommendations, workflow, dashboard, and agents
- Data layer
  - SQLAlchemy models and ORM
  - database session management and connection configuration
- Schema layer
  - Pydantic request/response validation models
- Business layer
  - service modules implementing create/read/update/delete operations
  - notification and workflow orchestration logic
- Workflow layer
  - mission state and workflow transitions
  - route assessment and risk generation
- Vectorstore layer
  - optional ChromaDB client
  - embedding support via OpenAI
- Configuration and logging
  - centralized settings
  - structured logging configuration

## Components

### API Routes
- `app.api.routes.*`
- expose REST endpoints for operational entities
- use dependency injection for authentication and data access

### Authentication
- OAuth2 Password flow using JWT tokens
- token generation and payload verification
- current user and role-based access checks

### Database
- SQLAlchemy ORM models in `app.models`
- database connection and session lifecycle in `app.database`
- support for SQLite locally and PostgreSQL in production

### Models
- `User`
- `Event`
- `Risk`
- `Route`
- `Recommendation`

### Schemas
- Pydantic schemas for input validation and response serialization
- separate create/update/read models per entity

### Services
- encapsulate business logic outside route handlers
- event, risk, route, recommendation, notification, and agent service modules

### Workflow
- `MaritimeWorkflow` orchestrates cross-cutting workflows
- `WorkflowState` manages mission status transitions and history

### Vectorstore
- optional semantic search support via ChromaDB
- embedding generation through OpenAI
- retrieval and document indexing capabilities

## Data Flow

1. Client sends request to API endpoint
2. API validates payload using Pydantic schema
3. Authentication dependency verifies JWT and current user
4. Service layer performs business operations against the database
5. Workflow components may generate related risks or recommendations
6. Notifications are dispatched for high-severity events
7. Response is returned as structured JSON

## Integration Points

- External authentication credentials managed via environment settings
- Optional OpenAI API integration for embeddings
- Optional ChromaDB persistence directory for vector data
- Potential future integration with external telemetry, navigation, or alerting systems

## Security

- Secrets and configuration loaded from environment variables or `.env`
- JWT-based OAuth2 authentication
- Role-based access for protected endpoints
- No credentials stored in source control

## Deployment Considerations

- Run with Uvicorn to serve the FastAPI application
- Use SQLite for local development
- Deploy PostgreSQL for production
- Mount persistent storage for optional ChromaDB data
- Expose health endpoint for readiness and monitoring

## Extensibility

The system design supports future extensions including:
- mission-level entities and state tracking
- advanced route validation and planning
- AI-assisted explanation and recommendation agents
- richer dashboard metrics and operational summaries
- integration with external maritime systems
```# filepath: d:\maritime-control-system\maritime-agentic-control-system\docs\architecture\system_design.md

# System Design

This document describes the overall architecture and system design for the Maritime Agentic Control System backend. It covers application layers, key services, data flow, integrations, and component responsibilities.

## Overview

The Maritime Agentic Control System is a modular FastAPI backend that enables maritime event logging, route planning, risk assessment, and recommendation generation. The system is designed to support:
- secure OAuth2 authentication
- relational database persistence
- service-oriented business logic
- workflow orchestration
- optional vector search and embeddings

## Architecture

The system uses a layered architecture with clear separation of concerns:

- API layer
  - FastAPI routes and request handling
  - path operations for events, risks, routes, recommendations, workflow, dashboard, and agents
- Data layer
  - SQLAlchemy models and ORM
  - database session management and connection configuration
- Schema layer
  - Pydantic request/response validation models
- Business layer
  - service modules implementing create/read/update/delete operations
  - notification and workflow orchestration logic
- Workflow layer
  - mission state and workflow transitions
  - route assessment and risk generation
- Vectorstore layer
  - optional ChromaDB client
  - embedding support via OpenAI
- Configuration and logging
  - centralized settings
  - structured logging configuration

## Components

### API Routes
- `app.api.routes.*`
- expose REST endpoints for operational entities
- use dependency injection for authentication and data access

### Authentication
- OAuth2 Password flow using JWT tokens
- token generation and payload verification
- current user and role-based access checks

### Database
- SQLAlchemy ORM models in `app.models`
- database connection and session lifecycle in `app.database`
- support for SQLite locally and PostgreSQL in production

### Models
- `User`
- `Event`
- `Risk`
- `Route`
- `Recommendation`

### Schemas
- Pydantic schemas for input validation and response serialization
- separate create/update/read models per entity

### Services
- encapsulate business logic outside route handlers
- event, risk, route, recommendation, notification, and agent service modules

### Workflow
- `MaritimeWorkflow` orchestrates cross-cutting workflows
- `WorkflowState` manages mission status transitions and history

### Vectorstore
- optional semantic search support via ChromaDB
- embedding generation through OpenAI
- retrieval and document indexing capabilities

## Data Flow

1. Client sends request to API endpoint
2. API validates payload using Pydantic schema
3. Authentication dependency verifies JWT and current user
4. Service layer performs business operations against the database
5. Workflow components may generate related risks or recommendations
6. Notifications are dispatched for high-severity events
7. Response is returned as structured JSON

## Integration Points

- External authentication credentials managed via environment settings
- Optional OpenAI API integration for embeddings
- Optional ChromaDB persistence directory for vector data
- Potential future integration with external telemetry, navigation, or alerting systems

## Security

- Secrets and configuration loaded from environment variables or `.env`
- JWT-based OAuth2 authentication
- Role-based access for protected endpoints
- No credentials stored in source control

## Deployment Considerations

- Run with Uvicorn to serve the FastAPI application
- Use SQLite for local development
- Deploy PostgreSQL for production
- Mount persistent storage for optional ChromaDB data
- Expose health endpoint for readiness and monitoring

## Extensibility

The system design supports future extensions including:
- mission-level entities and state tracking
- advanced route validation and planning
- AI-assisted explanation and recommendation agents
- richer dashboard metrics and operational summaries
- integration with external maritime systems
