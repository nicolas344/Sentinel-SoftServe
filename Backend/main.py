from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import actions, alerts, health, incidents

app = FastAPI(
    title="Sentinel-SoftServe API",
    description="Backend API para el proyecto Sentinel-SoftServe",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    # Dev note: the Vite dev server can be accessed as localhost, 127.0.0.1,
    # or a LAN IP (e.g. http://192.168.x.x:5173). If CORS doesn't include the
    # exact origin, browsers surface it as "TypeError: Failed to fetch".
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"^http://(\d{1,3}\.){3}\d{1,3}:5173$",
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
