# Maritime Agentic Control System

A control tower for maritime logistics. Governed AI agents watch live sea state, ship positions and port congestion; score risk; plan and compare routes on a digital twin of ports and shipping lanes; estimate fuel, cost and delay; and hold anything they are unsure about for a human to approve. Every agent action is checked, traced and audit-logged.

Backend: FastAPI, SQLAlchemy/Alembic, PostgreSQL (SQLite for tests). Frontend: React, Vite, Leaflet. Models: LightGBM, scikit-learn. Digital twin: NetworkX. Runs in Docker Compose.

> **This file is the source of truth for the figures below.** They are checked against the code by `backend/tests/test_readme_facts.py`, which fails if this README and the project disagree.

## By the numbers

| | |
|---|---|
| Agent classes in the code | **14** |
| ...registered with governance (identity, permissions, health, audit) | **10** |
| ...run as ungoverned services | **4** (Anomaly, Event Understanding, Simulation, Feedback) |
| Ports in the digital twin | **25** (20 with weekly congestion data, 5 Indian ports without) |
| Shipping lanes | **47** |
| Monitored sea-state corridors | **8** |
| Trained ML models served | **4** (congestion, fuel, anomaly, risk) |
| Frontend pages | **15** |
| API paths | **53** (58 operations) |
| Automated tests (at last update) | **542** (541 run; 1 needs optional packages) |

### The 14 agents

| Agent | Governed | What it does |
|---|---|---|
| Coordinator | yes | Runs the end-to-end workflow; skips route/decision steps for low-risk events |
| Ingestion | yes | Live sea state (Open-Meteo) for 8 corridors and AIS positions |
| Risk | yes | 0-100 hazard score per corridor (random forest, rule-based fallback) |
| Route | yes | Ranks routes over the digital twin by risk, cost, delay, emissions |
| Decision | yes | Recommendation with expected delay, cost change, risk reduction |
| Explanation | yes | Plain-language reasons (templates; optional OpenAI polish) |
| Congestion | yes | Port congestion classifier (LightGBM) |
| Delay | yes | Real lane transit statistics, plus live ETA/delay for your ships |
| Fuel | yes | Fuel burn, CO2 and cost at live bunker prices |
| Fleet Monitoring | yes | Follows operators' registered ships on live AIS, raises alerts |
| Anomaly | no | Isolation Forest over port congestion history |
| Event Understanding | no | Classifies news text and extracts locations |
| Simulation | no | What-if rerouting when a corridor is disrupted |
| Feedback | no | Records human decisions against agent executions |

### Model results (real, from `models/saved_models/*_metrics.json`)

| Model | Result | Baseline |
|---|---|---|
| Congestion (LightGBM classifier, 138,680 samples) | ROC-AUC **0.8168**, PR-AUC **0.6257** | no-skill PR-AUC 0.2072 |
| Fuel (LightGBM regressor, 1,440 rows) | R² **0.954**, MAE **626.6** litres | always-predict-the-mean MAE 3830.46 (83.6% lower) |
| Anomaly (Isolation Forest, 6,260 port-weeks) | flags 313 (5.0%) | unsupervised: 5% is its setting, not an accuracy score |
| Shipment delay (1,134 real container journeys) | not a model: lane statistics | lane median MAE 12.13 d; LightGBM 12.38 d did not beat it |

The fuel model only knows small Niger Delta craft; other ships and fuels use a labelled reference estimate (see Known limits).

## Quick start (about 5 minutes)

You need **Docker Desktop** and **Python 3** (only to run the setup script). No other installs.

```bash
git clone https://github.com/Shashank101-aiml/maritime-control-tower.git
cd maritime-control-tower
python scripts/bootstrap.py
docker compose up -d --build
```

`bootstrap.py` creates your private `.env` with freshly generated secrets and prints the admin password **once**. Then open **http://localhost** and sign in as `admin` with that password. Change it with:

```bash
docker compose exec backend python -m app.cli.set_password admin
```

Stop with `docker compose down`. Your data lives in a Docker volume and survives restarts.

Everything works without any API key. Live ships, bunker prices and news switch on when you add your own keys to `.env` (see Configuration); until then those features say they are off instead of showing invented data.

### If something goes wrong

| Symptom | Fix |
|---|---|
| "Cannot connect to the Docker daemon" | Start Docker Desktop and wait for "running" |
| "port is already allocated" | Set `FRONTEND_HOST_PORT`, `BACKEND_HOST_PORT` or `POSTGRES_HOST_PORT` in `.env`; if you change the frontend port, add `http://localhost:<port>` to `CORS_ORIGINS` |
| "container name ... already in use" | Another copy is running: `docker compose down`, or remove the old containers |
| "Missing POSTGRES_PASSWORD" | You have no `.env`: run `python scripts/bootstrap.py` |
| Backend exits with "SECRET_KEY ..." or "FIRST_SUPERUSER_PASSWORD ..." | Those `.env` values are missing or weak; fix them or delete `.env` and rerun bootstrap |
| Page looks stale after an update | `docker compose up -d --build`, then hard-refresh (Ctrl+F5) |
| Signed out and "too many attempts" | Five wrong passwords lock that account for 15 minutes from your address |

### Upgrading an existing checkout

If you already have a `.env` from an older version, run `python scripts/bootstrap.py`: it changes nothing but lists what needs fixing (a weak `SECRET_KEY`, a missing password). Two things to know:

- The database keeps the password it was first created with. To rotate it, set the new value in `.env` and also run `docker compose exec db psql -U maritime -d maritime -c "ALTER USER maritime PASSWORD '<new>'"` (with the database still on its old password), then `docker compose up -d`.
- An admin account created earlier with the password `admin` still works until you change it; the backend logs a warning at every start. Run `docker compose exec backend python -m app.cli.set_password admin`.

## Configuration (`.env`)

One file at the repo root, read by Docker Compose, the backend and Vite. It is git-ignored: never commit or share it.

| Key | Required | Meaning |
|---|---|---|
| `SECRET_KEY` | yes | 32+ random characters; signs login tokens. No default |
| `FIRST_SUPERUSER_USERNAME/EMAIL/PASSWORD` | yes, first start | The initial admin. Password: 12+ characters, not a common one. No default |
| `POSTGRES_USER/PASSWORD` | yes (Docker) | Database login. No default |
| `AISSTREAM_API_KEY` | no | Live ship positions ([aisstream.io](https://aisstream.io), free) |
| `OIL_PRICE_API` | no | Live bunker prices for Fuel & Cost ([oilpriceapi.com](https://www.oilpriceapi.com)) |
| `NEWS_API_KEY`, `WEATHER_API_KEY`, `OPENAI_API_KEY` | no | News, weather enrichment, LLM explanations |
| `ENABLE_LIVE_INGESTION` | no | `false` runs fully offline |
| `*_HOST_PORT` | no | Change published ports (defaults 80, 8001, 5433; all bound to 127.0.0.1) |

## What the app does

Fleet Overview, Corridors & Vessels, My Fleet, Event Monitor, Risk Analysis, Route Planning, Scenario Simulator, Congestion, Shipment Delay, Fuel & Cost, Agent Pipeline, Governance, Evaluation, User Management, Settings.

- **My Fleet**: register ships by IMO/MMSI; they are tracked on live AIS and placed on the digital twin.
- **Shipment Delay**: real lane statistics, and a live ETA for each of your ships against a due date you set or the ETA the crew broadcasts.
- **Fuel & Cost**: 20 ship classes, 6 fuels (VLSFO, HSFO, MGO, MDO, LNG, methanol), 51 routes, live bunker prices.
- **Governance**: agent registry, human approvals, execution trace, audit log; supervisors and admins see real totals.

## Roles

| Power | Operator | Supervisor | Admin |
|---|---|---|---|
| Run analyses, manage **own** vessels | yes | yes | yes |
| Read other fleets | no | read-only | yes |
| Approve/reject held agent actions; read audit and execution trace | no | yes | yes |
| Quarantine agents; manage users and roles | no | no | yes |

Enforced on the backend; hiding a button in the UI is never the only protection.

## Security and privacy

- `.env` is git-ignored and was never committed. Do not paste it, screenshot it, or share API keys.
- The app **refuses to start** with a missing/weak `SECRET_KEY`, and refuses to create an admin with a weak password.
- Failed sign-ins are throttled (5 per account per 15 minutes).
- Docker publishes all ports on `127.0.0.1` only, so the app is not reachable from your network.
- Validation errors never echo what you sent; server errors return a generic message and log the detail.
- `models/saved_models/*.joblib` are Python pickles and can run code when loaded. Only load them from a source you trust (this repository).
- The committed data files are derived, aggregate data (weekly port statistics; anonymised container journeys). Raw datasets are not included. Check each source dataset's licence before redistributing beyond the team.

## Run without Docker

Needs Python 3.14, Node 20 and a PostgreSQL database (SQLite works for tests only).

```bash
python scripts/bootstrap.py            # then set DATABASE_URL in .env to your Postgres
cd backend
python -m venv .venv && . .venv/bin/activate      # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm ci && npm run dev    # set VITE_API_BASE_URL=http://localhost:8000 in .env
```

## Tests

```bash
cd backend && pytest
```

CI (`.github/workflows/ci.yml`) runs the backend suite and a frontend build on every push. Tests need no `.env` and no network: they generate throwaway secrets and switch live ingestion off. One test that checks lanes never cross land needs `shapely`, `pyshp` and the Natural Earth coastline; run `python pipeline/check_lane_land.py` to check it yourself.

## Data and models

The trained models and the few data files the app reads at runtime are committed (about 11 MB), so a fresh clone works. Raw datasets are not; retraining needs them (`pipeline/`, see `docs/`). After changing a lane or waypoint, run `python pipeline/generate_sea_legs.py legs` then `python pipeline/check_lane_land.py` (0 of 47 lanes may cross land).

## Known limits

- Live ships come from AISStream's coastal receivers: dense near Europe and Singapore, absent over the Red Sea, Gulf and open ocean.
- Fuel: the trained model covers Niger Delta craft only; every other ship class uses approximate class burn rates (a labelled reference estimate, roughly plus or minus 30%).
- The risk scores are compressed: a "critical" corridor scores about 33/100, so the fleet risk tile rarely leaves the low range.
- Four agents run outside governance (see the table above).
- Sign-in throttling is per backend process, held in memory.

## Project structure

- `backend/app` : `api` routes, `agents`, `governance`, `twin` (ports, lanes, sea-only geometry), `fleet`, `fuel`, `models`, `schemas`, `core`, `cli`
- `frontend/src` : `pages`, `components`, `services`, `context`
- `pipeline/` : data cleaning, training, lane-geometry generation and checks
- `models/saved_models`, `data/` : runtime models and data
- `scripts/bootstrap.py` : first-time setup
- `docs/` : architecture notes

## License

No licence has been chosen yet; until one is added, all rights are reserved by the authors.
