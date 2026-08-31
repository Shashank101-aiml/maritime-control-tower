# filepath: database_design.md

# Database Design

This document describes the core relational database design for the Maritime Agentic Control System backend. The schema supports users, event logging, risk management, route planning, and recommendation tracking.

## Overview

The database is designed to:
- store user accounts and permissions
- capture maritime events
- record identified risks
- manage route plans
- generate and track recommendations
- support workflow and mission state transitions

The implementation is compatible with SQLite for local development and Postgres for production deployments.

## Tables

### users

Stores authenticated user accounts and access roles.

Columns:
- `id` — Integer, primary key
- `email` — String(256), unique, non-null
- `username` — String(50), unique, non-null
- `full_name` — String(128), nullable
- `hashed_password` — String(255), non-null
- `role` — Enum(`operator`, `supervisor`, `admin`), non-null, default `operator`
- `is_active` — Boolean, non-null, default `true`
- `is_superuser` — Boolean, non-null, default `false`
- `created_at` — DateTime, non-null, default current UTC timestamp
- `updated_at` — DateTime, non-null, default current UTC timestamp, on update current UTC timestamp

Indexes:
- unique index on `email`
- unique index on `username`

### events

Captures system events, alerts, and operational notifications.

Columns:
- `id` — Integer, primary key
- `timestamp` — DateTime, non-null, default current UTC timestamp
- `event_type` — String(50), non-null
- `severity` — String(20), non-null, default `info`
- `source` — String(100), nullable
- `description` — Text, nullable
- `created_by_id` — Integer, foreign key to `users.id`, nullable

Indexes:
- index on `event_type`
- index on `timestamp`

Relationships:
- optional many-to-one from `events` to `users`

### risks

Tracks risk assessments derived from events, routes, or operational status.

Columns:
- `id` — Integer, primary key
- `created_at` — DateTime, non-null, default current UTC timestamp
- `risk_type` — String(50), non-null, default `operational`
- `category` — String(50), nullable
- `description` — Text, nullable
- `likelihood` — String(30), non-null, default `medium`
- `impact` — String(30), non-null, default `medium`
- `estimated_cost` — Float, nullable
- `mitigation_plan` — Text, nullable
- `status` — String(30), non-null, default `open`
- `is_active` — Boolean, non-null, default `true`
- `created_by_id` — Integer, foreign key to `users.id`, nullable
- `event_id` — Integer, foreign key to `events.id`, nullable
- `route_id` — Integer, foreign key to `routes.id`, nullable

Indexes:
- index on `status`
- index on `risk_type`

Relationships:
- optional many-to-one from `risks` to `events`
- optional many-to-one from `risks` to `routes`
- optional many-to-one from `risks` to `users`

### recommendations

Stores follow-up recommendations generated from risk assessment and workflow logic.

Columns:
- `id` — Integer, primary key
- `created_at` — DateTime, non-null, default current UTC timestamp
- `recommendation_type` — String(50), non-null, default `operation`
- `summary` — String(255), non-null
- `details` — Text, nullable
- `priority` — Integer, non-null, default `0`
- `status` — String(30), non-null, default `pending`
- `source` — String(100), nullable
- `is_implemented` — Boolean, non-null, default `false`
- `created_by_id` — Integer, foreign key to `users.id`, nullable
- `risk_id` — Integer, foreign key to `risks.id`, nullable
- `route_id` — Integer, foreign key to `routes.id`, nullable

Indexes:
- index on `status`
- index on `priority`

Relationships:
- optional many-to-one from `recommendations` to `risks`
- optional many-to-one from `recommendations` to `routes`
- optional many-to-one from `recommendations` to `users`

### routes

Represents planned maritime routes and navigation plans.

Columns:
- `id` — Integer, primary key
- `created_at` — DateTime, non-null, default current UTC timestamp
- `origin` — String(128), non-null
- `destination` — String(128), non-null
- `status` — String(30), non-null, default `planned`
- `waypoints` — Text, nullable
- `estimated_time_of_arrival` — DateTime, nullable
- `notes` — Text, nullable
- `created_by_id` — Integer, foreign key to `users.id`, nullable

Indexes:
- index on `status`
- index on `origin`
- index on `destination`

Relationships:
- optional many-to-one from `routes` to `users`

### workflow_state (optional)

If the application tracks mission state history explicitly, a dedicated workflow state table is recommended.

Columns:
- `id` — Integer, primary key
- `mission_id` — Integer, foreign key to `routes.id` or another mission table
- `status` — String(30), non-null
- `details` — Text, nullable
- `timestamp` — DateTime, non-null, default current UTC timestamp

Indexes:
- index on `mission_id`
- index on `status`

## Entity Relationships

- One user may create many events, risks, recommendations, and routes.
- One event may be linked to zero or more risk records.
- One route may be linked to zero or more risk records and recommendations.
- One risk may generate zero or more recommendations.

## Notes

- Use explicit enum values for `role`, `risk_type`, `status`, and `recommendation_type`.
- Store timestamps in UTC.
- Keep the schema flexible enough to support additional maritime workflow entities such as missions, agents, and alert histories.
- For production, use Postgres with proper connection settings; in development, SQLite is acceptable.

This design provides a clean, normalized structure for the system's core domain models and supports the business workflows of event handling, risk assessment, and route recommendation.