````markdown
# API Endpoints

This document describes the main REST API endpoints exposed by the Maritime Agentic Control System backend.

## Root and Health

- `GET /`
  - Description: API root, typically returns service metadata or basic availability.
  - Response: JSON

- `GET /health`
  - Description: Health check endpoint.
  - Response: `{"status":"ok"}`

## Authentication

- `POST /token`
  - Description: OAuth2 password grant token endpoint.
  - Request: `username`, `password`
  - Response: `access_token`, `token_type`

## Events

- `GET /api/events`
  - Description: List events.
  - Query params: `skip`, `limit`
  - Authentication: required
  - Response: list of event objects

- `GET /api/events/{event_id}`
  - Description: Retrieve a single event by ID.

- `POST /api/events`
  - Description: Create a new event.
  - Body: event payload with `event_type`, `severity`, `source`, `description`

- `PUT /api/events/{event_id}`
  - Description: Update an existing event.

- `DELETE /api/events/{event_id}`
  - Description: Delete an event.

## Risks

- `GET /api/risks`
  - Description: List risk records.
  - Query params: `skip`, `limit`

- `GET /api/risks/{risk_id}`
  - Description: Retrieve a specific risk.

- `POST /api/risks`
  - Description: Create a new risk assessment.
  - Body: risk payload with `risk_type`, `category`, `description`, `likelihood`, `impact`, `estimated_cost`, `mitigation_plan`

- `PUT /api/risks/{risk_id}`
  - Description: Update risk details.

- `DELETE /api/risks/{risk_id}`
  - Description: Remove a risk record.

## Routes

- `GET /api/routes`
  - Description: List route plans.

- `GET /api/routes/{route_id}`
  - Description: Retrieve a single route.

- `POST /api/routes`
  - Description: Create a new route plan.
  - Body: route payload with `origin`, `destination`, `status`, `waypoints`, `estimated_time_of_arrival`, `notes`

- `PUT /api/routes/{route_id}`
  - Description: Update route details.

- `DELETE /api/routes/{route_id}`
  - Description: Delete a route plan.

## Recommendations

- `GET /api/recommendations`
  - Description: List recommendations.

- `GET /api/recommendations/{recommendation_id}`
  - Description: Retrieve a recommendation.

- `POST /api/recommendations`
  - Description: Create a recommendation.
  - Body: recommendation payload with `recommendation_type`, `summary`, `details`, `priority`, `status`, `source`, `is_implemented`

- `PUT /api/recommendations/{recommendation_id}`
  - Description: Update recommendation state.

- `DELETE /api/recommendations/{recommendation_id}`
  - Description: Remove a recommendation.

## Workflow

- `GET /api/workflow`
  - Description: Retrieve workflow or mission state summaries.
  - Response: workflow metadata, status, and history

- `POST /api/workflow`
  - Description: Execute workflow actions or transitions.

## Dashboard

- `GET /api/dashboard`
  - Description: Retrieve aggregated system metrics, risk summaries, and operational status.

## Agents

- `GET /api/agents`
  - Description: List available agent endpoints or agent metadata.

- `GET /api/agents/{agent_id}`
  - Description: Retrieve a specific agent's status or configuration.

## Notes

- Most endpoints are expected to require OAuth2 bearer authentication.
- All responses are JSON.
- CORS is enabled for integration with frontend applications.
```# filepath: d:\maritime-control-system\maritime-agentic-control-system\docs\api\endpoints.md

# API Endpoints

This document describes the main REST API endpoints exposed by the Maritime Agentic Control System backend.

## Root and Health

- `GET /`
  - Description: API root, typically returns service metadata or basic availability.
  - Response: JSON

- `GET /health`
  - Description: Health check endpoint.
  - Response: `{"status":"ok"}`

## Authentication

- `POST /token`
  - Description: OAuth2 password grant token endpoint.
  - Request: `username`, `password`
  - Response: `access_token`, `token_type`

## Events

- `GET /api/events`
  - Description: List events.
  - Query params: `skip`, `limit`
  - Authentication: required
  - Response: list of event objects

- `GET /api/events/{event_id}`
  - Description: Retrieve a single event by ID.

- `POST /api/events`
  - Description: Create a new event.
  - Body: event payload with `event_type`, `severity`, `source`, `description`

- `PUT /api/events/{event_id}`
  - Description: Update an existing event.

- `DELETE /api/events/{event_id}`
  - Description: Delete an event.

## Risks

- `GET /api/risks`
  - Description: List risk records.
  - Query params: `skip`, `limit`

- `GET /api/risks/{risk_id}`
  - Description: Retrieve a specific risk.

- `POST /api/risks`
  - Description: Create a new risk assessment.
  - Body: risk payload with `risk_type`, `category`, `description`, `likelihood`, `impact`, `estimated_cost`, `mitigation_plan`

- `PUT /api/risks/{risk_id}`
  - Description: Update risk details.

- `DELETE /api/risks/{risk_id}`
  - Description: Remove a risk record.

## Routes

- `GET /api/routes`
  - Description: List route plans.

- `GET /api/routes/{route_id}`
  - Description: Retrieve a single route.

- `POST /api/routes`
  - Description: Create a new route plan.
  - Body: route payload with `origin`, `destination`, `status`, `waypoints`, `estimated_time_of_arrival`, `notes`

- `PUT /api/routes/{route_id}`
  - Description: Update route details.

- `DELETE /api/routes/{route_id}`
  - Description: Delete a route plan.

## Recommendations

- `GET /api/recommendations`
  - Description: List recommendations.

- `GET /api/recommendations/{recommendation_id}`
  - Description: Retrieve a recommendation.

- `POST /api/recommendations`
  - Description: Create a recommendation.
  - Body: recommendation payload with `recommendation_type`, `summary`, `details`, `priority`, `status`, `source`, `is_implemented`

- `PUT /api/recommendations/{recommendation_id}`
  - Description: Update recommendation state.

- `DELETE /api/recommendations/{recommendation_id}`
  - Description: Remove a recommendation.

## Workflow

- `GET /api/workflow`
  - Description: Retrieve workflow or mission state summaries.
  - Response: workflow metadata, status, and history

- `POST /api/workflow`
  - Description: Execute workflow actions or transitions.

## Dashboard

- `GET /api/dashboard`
  - Description: Retrieve aggregated system metrics, risk summaries, and operational status.

## Agents

- `GET /api/agents`
  - Description: List available agent endpoints or agent metadata.

- `GET /api/agents/{agent_id}`
  - Description: Retrieve a specific agent's status or configuration.

## Notes

- Most endpoints are expected to require OAuth2 bearer authentication.
- All responses are JSON.
- CORS is enabled for integration with frontend applications.
