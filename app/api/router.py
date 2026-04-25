from fastapi import APIRouter

from app.api.routes import dashboard, invoices


api_router = APIRouter()
api_router.include_router(invoices.router)
api_router.include_router(dashboard.router)
