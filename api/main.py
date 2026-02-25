from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routes.graph import router as graph_router
from api.services.db import assert_expected_schema_version
from api.routes.labels import router as labels_router
from api.routes.alerts import router as alerts_router
from api.routes.entity import router as entity_router
from api.routes.search import router as search_router
from api.routes.cluster import router as cluster_router
from api.routes.metrics import router as metrics_router
from api.routes.alerts_actions import router as alerts_actions_router
from api.routes.runbook import router as runbook_router
from api.routes.risk import router as risk_router
from api.routes.dashboard import router as dashboard_router

app = FastAPI(title="BaseTrace API", version="0.1.0")

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
if WEB_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(WEB_DIR), html=True), name="ui")


@app.on_event("startup")
def _schema_guard():
    assert_expected_schema_version()


@app.get("/health")
def health():
    return {"ok": True, "service": "basetrace"}


app.include_router(graph_router, prefix="/graph", tags=["graph"])
app.include_router(labels_router, prefix="/labels", tags=["labels"])
app.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
app.include_router(alerts_actions_router, prefix="/alerts", tags=["alerts-actions"])
app.include_router(entity_router, prefix="/entity", tags=["entity"])
app.include_router(search_router, prefix="/search", tags=["search"])
app.include_router(cluster_router, prefix="/cluster", tags=["cluster"])
app.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
app.include_router(runbook_router, prefix="/runbook", tags=["runbook"])
app.include_router(risk_router, prefix="/entity", tags=["risk"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
