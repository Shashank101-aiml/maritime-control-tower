````markdown
# Risk Agent

The Risk Agent is responsible for identifying, evaluating, and prioritizing maritime risks across events, routes, and operational workflows. It supports the Maritime Agentic Control System by turning system signals into actionable risk assessments and escalation guidance.

## Purpose

- Analyze maritime events and route data for risk factors
- Quantify likelihood and impact for identified risks
- Prioritize risks for operational attention
- Provide guidance for mitigation and follow-up actions

## Responsibilities

- Detect risk triggers from high-severity events and route anomalies
- Assign risk categories, likelihood, and impact
- Maintain risk status throughout the workflow
- Recommend mitigation actions and escalation paths
- Feed risk findings into recommendations and notification mechanisms

## Typical Input

- Event details:
  - `event_type`
  - `severity`
  - `source`
  - `description`
- Route information:
  - `origin`
  - `destination`
  - `status`
  - `waypoints`
- System state and mission progress

## Expected Output

- Structured risk records with:
  - `risk_type`
  - `category`
  - `description`
  - `likelihood`
  - `impact`
  - `mitigation_plan`
  - `status`
- Priority assignments for follow-up
- Suggested recommendations and next steps

## Integration

The Risk Agent should be used in:

- event-driven risk assessment workflows
- route planning and mission review processes
- dashboard risk displays
- recommendation generation systems

## Design Principles

- Evidence-based: link risk findings to source events or route conditions
- Prioritized: surface the highest operational risks first
- Actionable: include mitigation advice and escalation instructions
- Traceable: preserve origin and status history of risk records

## Notes

This document describes the role and expected behavior of the Risk Agent. Implementation may be rule-based or augmented with additional analytics based on system architecture.
```# filepath: d:\maritime-control-system\maritime-agentic-control-system\docs\agents\risk_agent.md

# Risk Agent

The Risk Agent is responsible for identifying, evaluating, and prioritizing maritime risks across events, routes, and operational workflows. It supports the Maritime Agentic Control System by turning system signals into actionable risk assessments and escalation guidance.

## Purpose

- Analyze maritime events and route data for risk factors
- Quantify likelihood and impact for identified risks
- Prioritize risks for operational attention
- Provide guidance for mitigation and follow-up actions

## Responsibilities

- Detect risk triggers from high-severity events and route anomalies
- Assign risk categories, likelihood, and impact
- Maintain risk status throughout the workflow
- Recommend mitigation actions and escalation paths
- Feed risk findings into recommendations and notification mechanisms

## Typical Input

- Event details:
  - `event_type`
  - `severity`
  - `source`
  - `description`
- Route information:
  - `origin`
  - `destination`
  - `status`
  - `waypoints`
- System state and mission progress

## Expected Output

- Structured risk records with:
  - `risk_type`
  - `category`
  - `description`
  - `likelihood`
  - `impact`
  - `mitigation_plan`
  - `status`
- Priority assignments for follow-up
- Suggested recommendations and next steps

## Integration

The Risk Agent should be used in:

- event-driven risk assessment workflows
- route planning and mission review processes
- dashboard risk displays
- recommendation generation systems

## Design Principles

- Evidence-based: link risk findings to source events or route conditions
- Prioritized: surface the highest operational risks first
- Actionable: include mitigation advice and escalation instructions
- Traceable: preserve origin and status history of risk records

## Notes

This document describes the role and expected behavior of the Risk Agent. Implementation may be rule-based or augmented with additional analytics based on system architecture.
