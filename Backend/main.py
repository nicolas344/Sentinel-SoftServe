import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import actions, alerts, health, incidents
from services.recovery import start_recovery_loop

load_dotenv()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Rescata incidentes huérfanos (atascados por reinicios) al arrancar y cada 15 min.
    start_recovery_loop()
    yield


app = FastAPI(
    title="Sentinel-SoftServe API",
    description="Backend API para el proyecto Sentinel-SoftServe",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configurable por entorno:
#   CORS_ORIGINS       — lista separada por comas (ej. "https://sentinel-softserve-1.onrender.com")
#   CORS_ORIGIN_REGEX  — regex opcional para orígenes dinámicos
# Defaults: Vite dev server en localhost, 127.0.0.1 o una IP LAN. Si CORS no
# incluye el origen exacto, el navegador lo reporta como "TypeError: Failed to fetch".
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", _default_origins).split(",")
    if o.strip()
]
_cors_origin_regex = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"^http://(\d{1,3}\.){3}\d{1,3}:5173$",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents.router)
app.include_router(alerts.router)
app.include_router(actions.router)
app.include_router(health.router)


@app.get("/")
async def root():
    return {"message": "Bienvenido a Sentinel-SoftServe API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
