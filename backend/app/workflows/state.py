from datetime import datetime
from typing import Dict, List, Optional

from app.core.constants import MissionStatus


class StateTransitionError(Exception):
    """Raised when an invalid workflow state transition is attempted."""


class WorkflowState:
    _transitions = {
        MissionStatus.PENDING: [MissionStatus.IN_PROGRESS, MissionStatus.FAILED],
        MissionStatus.IN_PROGRESS: [MissionStatus.COMPLETED, MissionStatus.FAILED],
        MissionStatus.COMPLETED: [],
        MissionStatus.FAILED: [],
    }

    def __init__(
        self,
        status: MissionStatus = MissionStatus.PENDING,
        details: Optional[str] = None,
    ) -> None:
        self.status = status
        self.details = details or ""
        self.history: List[Dict[str, str]] = []
        self._record_transition(status, self.details)

    def _record_transition(self, status: MissionStatus, details: Optional[str]) -> None:
        self.history.append(
            {
                "status": status.value,
                "details": details or "",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        )

    def set_status(self, status: MissionStatus, details: Optional[str] = None) -> None:
        if status == self.status:
            self.details = details or self.details
            self._record_transition(status, self.details)
            return

        if not self.can_transition_to(status):
            raise StateTransitionError(
                f"Invalid transition from {self.status.value} to {status.value}"
            )

        self.status = status
        self.details = details or self.details
        self._record_transition(status, self.details)

    def can_transition_to(self, status: MissionStatus) -> bool:
        return status in self._transitions.get(self.status, [])

    def is_pending(self) -> bool:
        return self.status == MissionStatus.PENDING

    def is_in_progress(self) -> bool:
        return self.status == MissionStatus.IN_PROGRESS

    def is_completed(self) -> bool:
        return self.status == MissionStatus.COMPLETED

    def is_failed(self) -> bool:
        return self.status == MissionStatus.FAILED

    def is_terminal(self) -> bool:
        return self.status in {MissionStatus.COMPLETED, MissionStatus.FAILED}

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status.value,
            "details": self.details,
            "history": self.history,
        }
