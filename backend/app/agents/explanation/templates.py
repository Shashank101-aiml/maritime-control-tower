from typing import Dict, Sequence

EVENT_EXPLANATION_TEMPLATE = """
You are an Explanation Agent for a maritime control system.
Translate the following system state into a clear, concise explanation for operators.

Event details:
- Event type: {event_type}
- Severity: {severity}
- Source: {source}
- Description: {description}

{risk_section}
{route_section}
{recommendations_section}

Produce an explanation that includes:
- what happened
- why it matters
- any risk implications
- recommended next steps
- whether follow-up action is required
"""

RISK_EXPLANATION_TEMPLATE = """
You are an Explanation Agent for maritime risk management.
Summarize the risk information in a way that is actionable for operators.

Risk details:
- Risk type: {risk_type}
- Category: {category}
- Description: {description}
- Likelihood: {likelihood}
- Impact: {impact}
- Status: {status}
- Mitigation plan: {mitigation_plan}

{event_section}
{route_section}
{recommendations_section}

Explain:
- the nature of the risk
- the likely impact
- recommended mitigation steps
- any connection to current route or event context
"""

ROUTE_EXPLANATION_TEMPLATE = """
You are an Explanation Agent for maritime route planning.
Provide a clear summary of the route plan and any operational concerns.

Route details:
- Origin: {origin}
- Destination: {destination}
- Status: {status}
- Waypoints: {waypoints}
- Estimated ETA: {estimated_time_of_arrival}
- Notes: {notes}

{risk_section}
{recommendations_section}

Describe:
- route origin and destination
- current status
- potential hazards or risk factors
- suggested next steps or checks
"""

def render_recommendations_section(
    recommendations: Sequence[Dict[str, str]]
) -> str:
    if not recommendations:
        return "Recommendations:\n- None available."
    lines = ["Recommendations:"]
    for rec in recommendations:
        lines.append(
            "- {summary} (status: {status}, source: {source})".format(
                summary=rec.get("summary", "No summary provided"),
                status=rec.get("status", "unknown"),
                source=rec.get("source", "unknown source"),
            )
        )
    return "\n".join(lines)

def render_optional_section(title: str, data: Dict[str, str]) -> str:
    if not data:
        return ""
    lines = [f"{title}:"]
    for key, value in data.items():
        if value is None or value == "":
            continue
        lines.append(f"- {key.replace('_', ' ').capitalize()}: {value}")
    return "\n".join(lines)