"""Access code gate for shared deployments (e.g. HuggingFace Spaces)."""

from __future__ import annotations

import hashlib
import logging
import os
from string import Template

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from fastapi import FastAPI

logger = logging.getLogger(__name__)

ACCESS_CODE = os.environ.get("ACCESS_CODE", "").strip()
COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

print(f"[auth] Access gate: {'ENABLED' if ACCESS_CODE else 'DISABLED (no ACCESS_CODE set)'}")


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


_GATE_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Access — DTIC Research Landscape Explorer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/style.css?v=5">
  <style>
    .gate-wrap {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
    }
    .gate-card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 2.5rem 2rem;
      max-width: 400px;
      width: 100%;
      text-align: center;
    }
    .gate-card h1 {
      font-family: var(--font-display);
      font-size: 1.3rem;
      font-weight: 400;
      margin-bottom: 0.4rem;
    }
    .gate-card p {
      font-size: 0.82rem;
      color: var(--text-muted);
      margin-bottom: 1.5rem;
    }
    .gate-card input[type="password"] {
      width: 100%;
      padding: 0.65rem 0.85rem;
      background: var(--slate-900);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      color: var(--text);
      font-family: var(--font-mono);
      font-size: 0.9rem;
      text-align: center;
      margin-bottom: 1rem;
    }
    .gate-card input:focus {
      outline: none;
      border-color: var(--border-focus);
      box-shadow: 0 0 0 2px rgba(212, 168, 83, 0.15);
    }
    .gate-card button {
      width: 100%;
      padding: 0.75rem;
      background: var(--accent);
      color: var(--slate-950);
      border: none;
      border-radius: var(--radius);
      font-family: var(--font-body);
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
    }
    .gate-card button:hover {
      background: var(--accent-hover);
    }
    .gate-error {
      color: var(--red-500);
      font-size: 0.8rem;
      margin-bottom: 1rem;
    }
  </style>
</head>
<body>
  <div class="bg-grid" aria-hidden="true"></div>
  <div class="gate-wrap">
    <div class="gate-card">
      <h1>Research Landscape Explorer</h1>
      <p>Enter your access code to continue.</p>
      $error
      <form method="post" action="/gate">
        <input type="password" name="code" placeholder="Access code" autofocus required>
        <button type="submit">Enter</button>
      </form>
    </div>
  </div>
</body>
</html>
""")


class AccessGateMiddleware(BaseHTTPMiddleware):
    """Redirects unauthenticated requests to the gate page.

    If ACCESS_CODE is not set the middleware is a no-op (local dev mode).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if not ACCESS_CODE:
            return await call_next(request)

        path = request.url.path

        # Allow gate routes and static assets through
        if path == "/gate" or path.startswith("/static"):
            return await call_next(request)

        token = request.cookies.get(COOKIE_NAME, "")
        if token == _hash_code(ACCESS_CODE):
            return await call_next(request)

        return RedirectResponse("/gate", status_code=303)


def register_gate_routes(app: FastAPI) -> None:
    """Register GET /gate and POST /gate on the app."""

    @app.get("/gate", response_class=HTMLResponse)
    async def gate_page():
        return _GATE_TEMPLATE.substitute(error="")

    @app.post("/gate")
    async def gate_submit(request: Request):
        form = await request.form()
        code = str(form.get("code", "")).strip()
        print(f"[auth] Gate attempt: code_len={len(code)}, access_code_set={bool(ACCESS_CODE)}")

        if ACCESS_CODE and code == ACCESS_CODE:
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(
                COOKIE_NAME,
                _hash_code(ACCESS_CODE),
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                secure=True,
                samesite="none",
            )
            return response

        html = _GATE_TEMPLATE.substitute(
            error='<div class="gate-error">Invalid access code.</div>'
        )
        return HTMLResponse(html, status_code=403)
