"""Shared helper so every training script's real computed metrics
survive past the terminal they were printed to (spec section 29/30) --
previously every pipeline/train_*_model.py script printed its
ROC-AUC/PR-AUC/MAE/etc. and then lost them the moment the process
exited. Nothing here computes a new number; it persists the same real
values each script already calculates.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

METRICS_DIR = Path(__file__).resolve().parents[1] / "models" / "saved_models"


def save_metrics(name: str, metrics: Dict[str, Any]) -> Path:
    """Writes <name>_metrics.json next to <name>_model.joblib. Adds
    trained_at (UTC) so a stale metrics file is identifiable as such,
    not silently presented as current."""
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    path = METRICS_DIR / f"{name}_metrics.json"
    payload = {**metrics, "trained_at": datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(payload, indent=2))
    return path
