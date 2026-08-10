from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, insights, metrics

app = FastAPI(title="InsightFlow", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics.router)
app.include_router(insights.router)
app.include_router(chat.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
