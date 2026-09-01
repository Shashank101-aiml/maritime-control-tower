"""Shared rate limiter.

Kept in its own module so route modules can import the limiter without
importing app.main (which imports the routers — a circular import).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(key_func=get_remote_address)

# Applied to the model-inference and workflow routes: they are the
# expensive ones (model prediction, agent orchestration, live feed calls).
RATE_LIMIT = f"{settings.RATE_LIMIT_PER_MINUTE}/minute"
