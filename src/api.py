"""FastAPI app for local development and testing."""

from __future__ import annotations

import logging

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.models import MilitaryBranch, UserProposal
from src.pipeline import run_pipeline
from src.auth import AccessGateMiddleware, register_gate_routes

app = FastAPI(title="DTIC Research Landscape Analyzer", version="0.2.0")

app.add_middleware(AccessGateMiddleware)
register_gate_routes(app)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


class ExploreRequest(BaseModel):
    title: str
    topic_description: str = ""
    abstract: str = ""
    keywords: list[str] = Field(default_factory=list)
    military_branch: MilitaryBranch = MilitaryBranch.NAVY
    additional_context: str = ""


async def _run_explore(request: ExploreRequest):
    proposal = UserProposal(
        title=request.title,
        abstract=request.abstract,
        topic_description=request.topic_description,
        keywords=request.keywords,
        military_branch=request.military_branch,
        additional_context=request.additional_context,
    )
    report, markdown, summary = await run_pipeline(proposal)
    return {
        "verdict": report.verdict.value,
        "confidence": report.confidence,
        "markdown": markdown,
        "summary": report.executive_summary,
        "step_summary": summary,
        "report": report.model_dump(),
    }


@app.post("/api/explore")
async def explore(request: ExploreRequest):
    return await _run_explore(request)


@app.post("/api/analyze")
async def analyze(request: ExploreRequest):
    """Backward-compatible alias for /api/explore."""
    return await _run_explore(request)
