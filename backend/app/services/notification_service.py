from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def send_notification(
    title: str,
    message: str,
    recipients: Optional[List[str]] = None,
    channel: str = "email",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    recipients = recipients or []
    metadata = metadata or {}

    notification_payload = {
        "title": title,
        "message": message,
        "recipients": recipients,
        "channel": channel,
        "metadata": metadata,
    }

    logger.info("Dispatching notification", extra={"notification": notification_payload})

    # Placeholder for real notification integration (email, SMS, webhook, etc.)
    return {"status": "sent", "notification": notification_payload}


def notify_event_alert(
    event_type: str,
    severity: str,
    source: Optional[str] = None,
    description: Optional[str] = None,
    recipients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    title = f"Event alert: {event_type}"
    message = f"[{severity}] {description or 'No description provided.'}"
    metadata = {"event_type": event_type, "severity": severity, "source": source}
    return send_notification(title, message, recipients=recipients, channel="alert", metadata=metadata)