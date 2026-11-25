from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, internal, orders, paypal
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.5.0",
    description="Backend API for ZUNPY Automated Jobs. JOB-001: Invoice PDF to structured CSV.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://zunpyai.com", "https://www.zunpyai.com"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-ZUNPY-Order-Token"],
)

app.include_router(health.router)
app.include_router(paypal.router, prefix=settings.api_prefix)
app.include_router(orders.router, prefix=settings.api_prefix)
app.include_router(internal.router, prefix=settings.api_prefix)
