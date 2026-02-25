# BaseTrace

**Security intelligence graph for Base ecosystem flows.**

BaseTrace maps address relationships, fund flows, and suspicious concentration patterns on Base.

## MVP
- Ingest Base transactions and logs
- Entity labeling with confidence scores
- Flow graph API and UI-ready endpoints
- Alerting for:
  - sudden fan-out/fan-in (24h vs previous 24h delta)
  - high-centrality new nodes
  - anomalous bridge transfer paths (next iteration)

## Quickstart
```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8080
```

## Docker Compose
```bash
cp .env.example .env
docker compose up --build
```

Services:
- API: `http://localhost:8080`
- Postgres: `localhost:5432`
- Ingestor worker: continuous block + log ingestion

## Endpoints (v0)
- `GET /health`
- `GET /metrics`
- `GET /runbook/ingest`
- `GET /runbook/alerts`
- `GET /graph/neighbors/{address}`
- `GET /labels/{address}`
- `GET /entity/{address}`
- `GET /search?q=...`
- `GET /cluster/{address}`
- `GET /alerts/recent?status=new|ack|resolved`
- `GET /alerts/queue?status=new`
- `GET /alerts/{address}?status=new|ack|resolved`
- `POST /alerts/{id}/ack?assignee=<name>`
- `POST /alerts/{id}/resolve?assignee=<name>`

## Roadmap
See `docs/roadmap.md` and `docs/architecture.md`.
