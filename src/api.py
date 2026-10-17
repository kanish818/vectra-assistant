"""FastAPI wrapper around answer() plus the static chat UI.

Deliberately thin: all AI logic stays in src/answer.py + src/guardrails.py.
The API exists so a browser can call the same public function an evaluator
would call:

    uvicorn src.api:app            # UI at http://localhost:8000
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.answer import answer_with_details
from src.guardrails import mask_pii

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Vectra KB assistant", version="1.0.0")


class AskRequest(BaseModel):
    question: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/style.css")
def stylesheet() -> FileResponse:
    return FileResponse(STATIC_DIR / "style.css")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(STATIC_DIR / "app.js")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/ask")
def ask(req: AskRequest) -> dict:
    """One call = one answer() invocation + the metadata the UI renders."""
    started = time.perf_counter()
    result = answer_with_details(req.question)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "question": req.question,
        "masked_question": mask_pii(req.question),
        "answer": result["answer"],
        "citations": result["citations"],
        "abstained": result["abstained"],
        "retrieved": result["retrieved"],
        "warnings": result["warnings"],
        "latency_ms": latency_ms,
    }
