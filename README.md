# BaseTrace

**Security intelligence graph for Base ecosystem flows.**

BaseTrace maps address relationships, fund flows, and suspicious concentration patterns on Base.

## MVP
- Ingest Base transactions and logs
- Entity labeling with confidence scores
- Flow graph API and UI-ready endpoints
- Alerting for:
  - sudden fan-out/fan-in
  - high-centrality new nodes
  - anomalous bridge transfer paths

## Quickstart
```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8080
```

## Endpoints (v0)
- `GET /health`
- `GET /graph/neighbors/{address}`
- `GET /labels/{address}`
- `GET /alerts/recent`

## Roadmap
See `docs/roadmap.md` and `docs/architecture.md`.
