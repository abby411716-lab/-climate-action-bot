from fastapi import FastAPI

from app.database import Base, engine
from app.routers import webhook

Base.metadata.create_all(bind=engine)

app = FastAPI(title="氣候行動學習互動網站 API")
app.include_router(webhook.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
