# Explanation Agent

The Explanation Agent is responsible for converting maritime system state, events, risks, and route planning data into clear, human-readable explanations. Its role is to help operators, supervisors, and stakeholders understand why a decision was made, what a system alert means, and what the recommended next steps are.

## Purpose

- Provide context for event alerts and risk assessments.
- Translate technical system outputs into operational language.
- Support decision-making with concise explanations and reasoning.
- Improve situational awareness across the maritime control workflow.

## Responsibilities

- Interpret event details such as severity, source, and description.
- Summarize route planning and operational mission status.
- Explain risk findings and the reasoning behind mitigation recommendations.
- Generate actionable guidance based on system state and workflow transitions.

## Typical Input

The agent may consume:

- Event metadata:
  - `event_type`
  - `severity`
  - `source`
  - `description`
- Risk assessment data:
  - `risk_type`
  - `likelihood`
  - `impact`
  - `status`
  - `mitigation_plan`
- Route data:
  - `origin`
  - `destination`
  - `status`
  - `waypoints`
- Recommendation summaries

## Expected Output

The output should be a structured explanation, for example:

- A summary of what happened
- Why it is important
- What risk factors are involved
- Recommended operator actions
- Any follow-up or escalation notes

Example:

- "A high-severity navigation alert was detected on route segment 3. The route has elevated risk due to rapidly changing weather and the vessel's planned speed. We recommend reducing speed, verifying waypoint clearance, and coordinating with the bridge team."

## Integration

The Explanation Agent should be used in:

- alert notification workflows
- risk review dashboards
- route planning summaries
- operator briefing interfaces

## Design Principles

- Clear: avoid jargon where possible
- Accurate: reflect the actual system state
- Actionable: provide next-step guidance
- Traceable: reference the trigger event or risk source

## Notes

This document is intended to describe the agent's role and expected behavior. Implementation details depend on the system architecture and the chosen explanation strategy, whether rule-based or AI-assisted.