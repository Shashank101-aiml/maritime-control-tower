from fastapi import APIRouter, HTTPException

from app.agents.anomaly.anomaly_agent import get_anomaly_agent

router = APIRouter()


@router.get("/anomalies")
def get_anomalies():
    """Real anomaly score for every port with congestion history --
    each port's most recent real weekly snapshot, scored by the trained
    Isolation Forest against that port's own history. Sorted most
    anomalous first (lowest score = most anomalous).
    """
    agent = get_anomaly_agent()
    if not agent.is_available:
        raise HTTPException(503, "Anomaly model is not available -- run pipeline/train_anomaly_model.py.")

    reports = [agent.detect(port).model_dump() for port in agent.known_ports]
    reports.sort(key=lambda r: r["anomaly_score"])
    return {"anomalies": reports}


@router.get("/anomalies/{port}")
def get_anomaly_for_port(port: str):
    agent = get_anomaly_agent()
    if not agent.is_available:
        raise HTTPException(503, "Anomaly model is not available -- run pipeline/train_anomaly_model.py.")
    try:
        return agent.detect(port).model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))
