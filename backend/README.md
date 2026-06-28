# SwarmMon Backend

FastAPI service for event ingestion, fleet state, incidents, and scenario reports.

## Setup (Conda)

```bash
conda create -n swarmmon python=3.11 -y
conda activate swarmmon
cd backend
pip install -e ".[dev]"
```

## Setup (venv)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
pip install -e ".[dev]"
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Configuration

Environment variables (prefix `SWARMMON_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./swarmmon.db` | SQLModel database URL |
| `HEARTBEAT_TIMEOUT_SECONDS` | `30` | Robot offline threshold |
| `SCENARIOS_DIR` | `../simulation/scenarios` | Scenario YAML directory |
| `CORS_ORIGINS` | `localhost:5173` | Dashboard origins |

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/events/batch` | Ingest normalized events |
| GET | `/api/v1/fleet` | Fleet robot state |
| GET | `/api/v1/fleet/summary` | Aggregated health counts |
| GET | `/api/v1/robots/{id}?scenario_run_id=` | Single robot detail |
| GET | `/api/v1/incidents` | List incidents |
| POST | `/api/v1/scenarios/runs` | Create scenario run |
| POST | `/api/v1/scenarios/runs/from-yaml` | Create run from scenario YAML |
| GET | `/api/v1/scenarios/runs` | List scenario runs |
| GET | `/api/v1/scenarios/runs/{id}` | Get scenario run |
| POST | `/api/v1/scenarios/runs/{id}/complete` | Complete run + offline check |
| GET | `/api/v1/scenarios/runs/{id}/report` | Scenario report |

## Scenario from YAML

```bash
curl -X POST http://localhost:8000/api/v1/scenarios/runs/from-yaml \
  -H "Content-Type: application/json" \
  -d '{"scenario_run_id": "run-001", "scenario_name": "warehouse_amr_observability_test"}'
```

Loads `simulation/scenarios/warehouse_amr_observability_test.yaml` and stores expected outcomes for report validation.

## Tests

```bash
pytest -q
```

## Project Layout

```text
backend/
  app/
    main.py                 # FastAPI app
    schemas.py              # Pydantic event/API models
    models.py               # SQLModel tables
    health_rules.py         # Health engine + state updater
    incident_engine.py      # Incident timelines
    scenario_report_engine.py
    scenario_loader.py      # YAML → scenario run
    fleet_summary.py        # Fleet aggregation
    routers/
```
