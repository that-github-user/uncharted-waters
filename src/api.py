"""FastAPI app for local development and testing."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.models import MilitaryBranch, UserProposal
from src.pipeline import run_pipeline

app = FastAPI(title="DTIC Uniqueness Analyzer", version="0.1.0")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


class AnalyzeRequest(UserProposal):
    pass


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest):
    proposal = UserProposal(
        title=request.title,
        abstract=request.abstract,
        keywords=request.keywords,
        military_branch=request.military_branch,
        additional_context=request.additional_context,
    )
    report, markdown, summary = await run_pipeline(proposal)
    return {
        "verdict": report.verdict.value,
        "confidence": report.confidence,
        "markdown": markdown,
        "summary": summary,
        "report": report.model_dump(),
    }
