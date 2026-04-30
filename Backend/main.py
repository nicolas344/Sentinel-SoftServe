import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import alerts, incidents

app = FastAPI(
    title="Sentinel-SoftServe API",
    description="Backend API para el proyecto Sentinel-SoftServe",
    version="1.0.0",
)

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents.router)
app.include_router(alerts.router)


@app.get("/")
async def root():
    return {"message": "Bienvenido a Sentinel-SoftServe API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
