from enum import Enum


class UserRole(str, Enum):
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class MissionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


DEFAULT_CACHE_TTL_SECONDS = 300
MAX_COMMAND_RETRIES = 3
DEFAULT_PAGE_SIZE = 25
