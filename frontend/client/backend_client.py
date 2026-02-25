"""
HTTP client async hacia el backend FastAPI.
Todas las llamadas son async (httpx.AsyncClient).
"""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")
_TIMEOUT = 120.0  # segundos


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BACKEND_URL, timeout=_TIMEOUT)


async def upload_template(session_id: str, role: str, filename: str, content: bytes) -> dict:
    async with _client() as c:
        r = await c.post(
            "/api/upload/template",
            data={"session_id": session_id, "role": role},
            files={"file": (filename, content, "application/pdf")},
        )
        r.raise_for_status()
        return r.json()


async def upload_excel(session_id: str, filename: str, content: bytes) -> dict:
    async with _client() as c:
        r = await c.post(
            "/api/upload/excel",
            data={"session_id": session_id},
            files={"file": (filename, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        r.raise_for_status()
        return r.json()


async def analyze_template(session_id: str, role: str) -> dict:
    async with _client() as c:
        r = await c.post(
            "/api/analyze/template",
            json={"session_id": session_id, "role": role},
        )
        r.raise_for_status()
        return r.json()


async def analyze_excel(session_id: str) -> dict:
    async with _client() as c:
        r = await c.post(
            f"/api/analyze/excel?session_id={session_id}",
        )
        r.raise_for_status()
        return r.json()


async def generate_preview(
    session_id: str,
    role: str,
    qr_x: int,
    qr_y: int,
    qr_size: int,
) -> dict:
    async with _client() as c:
        r = await c.post(
            "/api/preview/",
            json={
                "session_id": session_id,
                "role": role,
                "qr_x": qr_x,
                "qr_y": qr_y,
                "qr_size": qr_size,
            },
        )
        r.raise_for_status()
        return r.json()


async def start_generation(
    session_id: str,
    positions: dict,
    column_map: dict,
    incremental: bool = True,
) -> dict:
    async with _client() as c:
        r = await c.post(
            "/api/generate",
            json={
                "session_id": session_id,
                "positions": positions,
                "column_map": column_map,
                "incremental": incremental,
            },
        )
        r.raise_for_status()
        return r.json()


async def get_job_status(job_id: str) -> dict:
    async with _client() as c:
        r = await c.get(f"/api/status/{job_id}")
        r.raise_for_status()
        return r.json()
