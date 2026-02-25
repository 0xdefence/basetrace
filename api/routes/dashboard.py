from fastapi import APIRouter

from api.services.dashboard_service import dashboard_summary

router = APIRouter()


@router.get("/summary")
def get_dashboard_summary(hot_limit: int = 5):
    return dashboard_summary(hot_limit=hot_limit)
