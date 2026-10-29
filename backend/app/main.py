from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_ORIGINS
from app.services.gee_client import init_gee, is_gee_initialized
from app.routers import biodiversity, imagery, point_analysis, cascade, impact

app = FastAPI(title="TwinEarth API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    try:
        init_gee()
    except Exception as error:
        app.state.gee_error = str(error)


@app.get("/api/health")
def health():
    return {"status": "ok", "gee_ready": is_gee_initialized()}


app.include_router(imagery.router, prefix="/api")
app.include_router(point_analysis.router, prefix="/api")
app.include_router(cascade.router, prefix="/api")
app.include_router(biodiversity.router, prefix="/api")
app.include_router(impact.router, prefix="/api")
