from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import admin, webhook
from app.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield


app = FastAPI(title="氣候行動學習互動網站 API", lifespan=lifespan)
app.include_router(webhook.router)
app.include_router(admin.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
