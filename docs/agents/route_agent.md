````markdown
# Route Agent

The Route Agent is responsible for generating, validating, and monitoring maritime route plans within the Maritime Agentic Control System. It helps coordinate voyage planning, assess route risks, and provide guidance for safe and efficient navigation.

## Purpose

- Create and manage planned routes for maritime operations
- Validate route details for completeness and feasibility
- Monitor route status and integrate route data with risk assessment
- Support dynamic route updates and mission planning

## Responsibilities

- Receive route creation requests with origin, destination, and waypoints
- Validate route metadata and operational status
- Store route plans for workflow and risk integration
- Coordinate with risk and recommendation agents to flag route concerns
- Track route transitions and support updates or cancellations

## Typical Input

- Route payloads:
  - `origin`
  - `destination`
  - `status`
  - `waypoints`
  - `estimated_time_of_arrival`
  - `notes`

## Expected Output

- Persisted route plan records
- Route summaries suitable for dashboard and workflow processing
- Validated route metadata ready for risk analysis
- Updates and deletions applied to managed route plans

## Integration

The Route Agent should be used in:

- route planning APIs
- workflow services that assess mission status
- risk assessment pipelines
- recommendation generation

## Design Principles

- Clear: keep route definitions explicit and structured
- Reliable: validate route attributes before persistence
- Integrated: link route plans with risk and recommendation workflows
- Flexible: support route updates as mission requirements change

## Notes

This document describes the Route Agent’s expected role and behavior within the Maritime Agentic Control System. Implementation may evolve to include more advanced navigation validation or external charting integrations.
```# filepath: d:\maritime-control-system\maritime-agentic-control-system\docs\agents\route_agent.md

# Route Agent

The Route Agent is responsible for generating, validating, and monitoring maritime route plans within the Maritime Agentic Control System. It helps coordinate voyage planning, assess route risks, and provide guidance for safe and efficient navigation.

## Purpose

- Create and manage planned routes for maritime operations
- Validate route details for completeness and feasibility
- Monitor route status and integrate route data with risk assessment
- Support dynamic route updates and mission planning

## Responsibilities

- Receive route creation requests with origin, destination, and waypoints
- Validate route metadata and operational status
- Store route plans for workflow and risk integration
- Coordinate with risk and recommendation agents to flag route concerns
- Track route transitions and support updates or cancellations

## Typical Input

- Route payloads:
  - `origin`
  - `destination`
  - `status`
  - `waypoints`
  - `estimated_time_of_arrival`
  - `notes`

## Expected Output

- Persisted route plan records
- Route summaries suitable for dashboard and workflow processing
- Validated route metadata ready for risk analysis
- Updates and deletions applied to managed route plans

## Integration

The Route Agent should be used in:

- route planning APIs
- workflow services that assess mission status
- risk assessment pipelines
- recommendation generation

## Design Principles

- Clear: keep route definitions explicit and structured
- Reliable: validate route attributes before persistence
- Integrated: link route plans with risk and recommendation workflows
- Flexible: support route updates as mission requirements change

## Notes

This document describes the Route Agent’s expected role and behavior within the Maritime Agentic Control System. Implementation may evolve to include more advanced navigation validation or external charting integrations.
