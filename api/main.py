from fastapi import FastAPI

from api.routes.graph import router as graph_router
from api.routes.labels import router as labels_router
from api.routes.alerts import router as alerts_router
from api.routes.entity import router as entity_router

app = FastAPI(title="BaseTrace API", version="0.1.0")


@app.get("/health")
def health():
    return {"ok": True, "service": "basetrace"}


app.include_router(graph_router, prefix="/graph", tags=["graph"])
app.include_router(labels_router, prefix="/labels", tags=["labels"])
app.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
app.include_router(entity_router, prefix="/entity", tags=["entity"])
