# BaseTrace Architecture (v0)

## Components
1. Ingestion worker (`ingest/base_ingest.py`)
2. Storage (Postgres, `sql/schema_v1.sql`)
3. Labeling engine (`labels/rules.py`)
4. Alert engine (`alerts/engine.py`)
5. API (`api/main.py`)

## Data flow
RPC -> ingest blocks/logs -> normalize tx/transfers -> store -> compute labels/edges -> evaluate alerts -> API/UI/webhooks

## v0 principles
- Start rule-based and explainable
- Confidence on every label
- Keep alerts high-signal
- Build for Base first, multi-chain later
- Use provider/self-hosted RPC for production; `mainnet.base.org` is rate-limited

## Base network references
- Mainnet chain ID: `8453`
- Public RPC: `https://mainnet.base.org` (rate-limited)
- Public explorer: `https://base.blockscout.com/`
- Known Base system contracts can be pre-labeled (bridge/treasury infra)
