"""README.md is the project's source of truth for its headline figures.
This fails when the README and the code disagree, so neither drifts."""

import json
import re
from pathlib import Path

from app.agents.ingestion.live_conditions_client import MONITORED_LOCATIONS
from app.twin.digital_twin import get_digital_twin

REPO = Path(__file__).resolve().parents[2]
README = (REPO / "README.md").read_text(encoding="utf-8")


def _row(label: str) -> str:
    match = re.search(rf"^\|\s*{re.escape(label)}[^|]*\|\s*\*\*([^|]+?)\*\*", README, flags=re.M)
    assert match, f"README has no '{label}' row"
    return match.group(1)


def _agent_classes():
    return sorted(
        re.findall(r"^class (\w+Agent)\b", path.read_text(encoding="utf-8"), flags=re.M)
        for path in (REPO / "backend" / "app" / "agents").rglob("*.py")
    )


def test_agent_counts_match_the_code():
    classes = [name for group in _agent_classes() for name in group]
    seeded = re.findall(r'"id": "[a-z\-]+-agent"', (REPO / "backend" / "app" / "main.py").read_text(encoding="utf-8"))
    assert len(classes) == 14 == int(_row("Agent classes in the code"))
    assert len(seeded) == 10 == int(_row("...registered with governance"))
    assert int(_row("...run as ungoverned services").split()[0]) == len(classes) - len(seeded)


def test_the_governed_and_ungoverned_tables_list_every_agent():
    ungoverned = {"Anomaly", "Event Understanding", "Simulation", "Feedback"}
    for name in ungoverned:
        assert re.search(rf"^\|\s*{name}\s*\|\s*no\s*\|", README, flags=re.M), name
    section = README.split("### The 14 agents", 1)[1].split("\n### ", 1)[0]
    assert len(re.findall(r"^\|[^|]+\|\s*yes\s*\|", section, flags=re.M)) == 10


def test_twin_and_corridor_counts_match():
    graph = get_digital_twin().graph
    assert int(_row("Ports in the digital twin").split()[0]) == graph.number_of_nodes()
    assert int(_row("Shipping lanes")) == graph.number_of_edges()
    assert int(_row("Monitored sea-state corridors")) == len(MONITORED_LOCATIONS)
    with_data = sum(1 for _, d in graph.nodes(data=True) if d["has_congestion_data"])
    assert f"{with_data} with weekly congestion data" in README


def test_page_count_matches_the_navigation():
    source = (REPO / "frontend" / "src" / "components" / "Sidebar.jsx").read_text(encoding="utf-8")
    assert len(re.findall(r"\{ id: '", source)) == int(_row("Frontend pages"))


def test_model_results_quoted_in_the_readme_are_the_saved_ones():
    metrics = {n: json.loads((REPO / "models" / "saved_models" / f"{n}_metrics.json").read_text()) for n in
               ("congestion", "fuel", "anomaly", "delay")}
    assert str(metrics["congestion"]["roc_auc"]) in README and str(metrics["congestion"]["pr_auc"]) in README
    assert str(metrics["congestion"]["no_skill_pr_auc"]) in README
    assert f"{metrics['congestion']['n_train'] + metrics['congestion']['n_test']:,}" in README
    assert str(metrics["fuel"]["r2"]) in README and str(metrics["fuel"]["mae"]) in README
    assert str(metrics["fuel"]["baseline_mean_mae"]) in README
    assert f"{metrics['fuel']['n_train'] + metrics['fuel']['n_test']:,}" in README
    assert str(metrics["anomaly"]["flagged_count"]) in README and f"{metrics['anomaly']['n_samples']:,}" in README
    assert f"{metrics['delay']['n_journeys']:,}" in README
    assert str(metrics["delay"]["transit_days"]["lane_median_mae_days"]) in README
    assert str(metrics["delay"]["transit_days"]["lightgbm_mae_days"]) in README


def test_no_default_credentials_are_documented():
    assert "FIRST_SUPERUSER_PASSWORD=admin" not in README
    assert "change-this-secret" not in README
