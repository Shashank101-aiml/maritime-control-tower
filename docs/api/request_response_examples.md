````markdown
# Request / Response Examples

This document provides example requests and responses for the Maritime Agentic Control System backend API.

## Authentication

### Request

`POST /token`

```http
POST /token HTTP/1.1
Content-Type: application/x-www-form-urlencoded

grant_type=password&username=admin@example.com&password=admin
```

### Response

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## Health Check

### Request

`GET /health`

```http
GET /health HTTP/1.1
Accept: application/json
```

### Response

```json
{
  "status": "ok"
}
```

---

## List Events

### Request

`GET /api/events`

```http
GET /api/events HTTP/1.1
Authorization: Bearer <access_token>
Accept: application/json
```

### Response

```json
[
  {
    "id": 1,
    "timestamp": "2026-07-07T12:34:56.789Z",
    "event_type": "navigation_alert",
    "severity": "warning",
    "source": "bridge_system",
    "description": "Route deviation detected near waypoint 4"
  }
]
```

---

## Create Event

### Request

`POST /api/events`

```http
POST /api/events HTTP/1.1
Content-Type: application/json
Authorization: Bearer <access_token>

{
  "event_type": "navigation_alert",
  "severity": "warning",
  "source": "bridge_system",
  "description": "Route deviation detected near waypoint 4"
}
```

### Response

```json
{
  "id": 2,
  "timestamp": "2026-07-07T12:45:01.234Z",
  "event_type": "navigation_alert",
  "severity": "warning",
  "source": "bridge_system",
  "description": "Route deviation detected near waypoint 4"
}
```

---

## List Risks

### Request

`GET /api/risks`

```http
GET /api/risks HTTP/1.1
Authorization: Bearer <access_token>
Accept: application/json
```

### Response

```json
[
  {
    "id": 1,
    "created_at": "2026-07-07T12:45:05.123Z",
    "risk_type": "operational",
    "category": "navigation_alert",
    "description": "Route deviation detected near waypoint 4",
    "likelihood": "high",
    "impact": "high",
    "estimated_cost": null,
    "mitigation_plan": "Review current route and verify navigation system.",
    "status": "open",
    "source": null,
    "is_active": true
  }
]
```

---

## Create Risk

### Request

`POST /api/risks`

```http
POST /api/risks HTTP/1.1
Content-Type: application/json
Authorization: Bearer <access_token>

{
  "risk_type": "operational",
  "category": "navigation_alert",
  "description": "Bridge alert for route deviation",
  "likelihood": "high",
  "impact": "high",
  "estimated_cost": 12000,
  "mitigation_plan": "Verify navigation systems and reroute as needed.",
  "status": "open",
  "is_active": true
}
```

### Response

```json
{
  "id": 2,
  "created_at": "2026-07-07T12:50:20.456Z",
  "risk_type": "operational",
  "category": "navigation_alert",
  "description": "Bridge alert for route deviation",
  "likelihood": "high",
  "impact": "high",
  "estimated_cost": 12000.0,
  "mitigation_plan": "Verify navigation systems and reroute as needed.",
  "status": "open",
  "source": null,
  "is_active": true
}
```

---

## List Routes

### Request

`GET /api/routes`

```http
GET /api/routes HTTP/1.1
Authorization: Bearer <access_token>
Accept: application/json
```

### Response

```json
[
  {
    "id": 1,
    "created_at": "2026-07-07T12:25:30.345Z",
    "origin": "Port Alpha",
    "destination": "Port Bravo",
    "status": "planned",
    "waypoints": "[{\"lat\": 12.34, \"lon\": 56.78}]",
    "estimated_time_of_arrival": "2026-07-08T08:00:00.000Z",
    "notes": "Maintain safe speed due to weather"
  }
]
```

---

## Create Route

### Request

`POST /api/routes`

```http
POST /api/routes HTTP/1.1
Content-Type: application/json
Authorization: Bearer <access_token>

{
  "origin": "Port Alpha",
  "destination": "Port Bravo",
  "status": "planned",
  "waypoints": "[{\"lat\": 12.34, \"lon\": 56.78}]",
  "estimated_time_of_arrival": "2026-07-08T08:00:00.000Z",
  "notes": "Maintain safe speed due to weather"
}
```

### Response

```json
{
  "id": 2,
  "created_at": "2026-07-07T12:55:10.789Z",
  "origin": "Port Alpha",
  "destination": "Port Bravo",
  "status": "planned",
  "waypoints": "[{\"lat\": 12.34, \"lon\": 56.78}]",
  "estimated_time_of_arrival": "2026-07-08T08:00:00.000Z",
  "notes": "Maintain safe speed due to weather"
}
```

---

## List Recommendations

### Request

`GET /api/recommendations`

```http
GET /api/recommendations HTTP/1.1
Authorization: Bearer <access_token>
Accept: application/json
```

### Response

```json
[
  {
    "id": 1,
    "created_at": "2026-07-07T12:57:40.123Z",
    "recommendation_type": "safety",
    "summary": "Verify navigation system after route deviation",
    "details": "Confirm GPS integrity and reroute as necessary.",
    "priority": 1,
    "status": "pending",
    "source": "risk:1",
    "is_implemented": false
  }
]
```

---

## Workflow Example

### Request

`POST /api/workflow`

```http
POST /api/workflow HTTP/1.1
Content-Type: application/json
Authorization: Bearer <access_token>

{
  "action": "assess_route",
  "route_id": 1
}
```

### Response

```json
{
  "message": "Workflow action executed",
  "data": {
    "status": "in_progress",
    "details": "Route assessment started"
  }
}
```

---

## Agents Endpoint

### Request

`GET /api/agents`

```http
GET /api/agents HTTP/1.1
Authorization: Bearer <access_token>
Accept: application/json
```

### Response

```json
[
  {
    "id": "risk_agent",
    "name": "Risk Agent",
    "description": "Evaluates maritime risks from events and routes."
  }
]
```

---

## Error Response

### Example

```json
{
  "detail": "Could not validate credentials"
}
```

### Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "event_type"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```
````
