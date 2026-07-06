from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import assets, assistant, detect, health, history, make, models, settings


app = FastAPI(
    title="AI Rice Disease Analysis Platform",
    description="AI rice disease monitoring and diagnosis backend",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(health.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(detect.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(make.router, prefix="/api")
app.include_router(settings.router, prefix="/api")

