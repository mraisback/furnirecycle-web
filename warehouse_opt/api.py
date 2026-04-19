from __future__ import annotations

import asyncio

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_db_session, init_db
from .realtime import RealtimeHub
from .schemas import JobAcceptedResponse, OptimizationRequest, OptimizationResult
from .service import OptimizationService

app = FastAPI(title=settings.app_name, version=settings.app_version)
hub = RealtimeHub()
service = OptimizationService(hub)


@app.on_event("startup")
async def startup() -> None:
    await init_db()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@app.post("/v1/optimize", response_model=JobAcceptedResponse)
async def create_optimization_job(
    payload: OptimizationRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> JobAcceptedResponse:
    job_id = await service.create_job(session, payload)

    async def run_job_background(jid: str) -> None:
        async for bg_session in get_db_session():
            await service.run_job(bg_session, jid)

    background.add_task(run_job_background, job_id)
    return JobAcceptedResponse(job_id=job_id, status="queued")


@app.get("/v1/optimize/{job_id}", response_model=OptimizationResult)
async def get_job(job_id: str, session: AsyncSession = Depends(get_db_session)) -> OptimizationResult:
    result = await service.get_result(session, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@app.websocket("/v1/optimize/{job_id}/stream")
async def job_stream(websocket: WebSocket, job_id: str) -> None:
    await hub.connect(job_id, websocket)
    try:
        while True:
            # Keep connection alive and allow client pings.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(job_id, websocket)
