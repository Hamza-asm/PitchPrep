"""Run with: python -m uvicorn app.main:create_app --factory --port 8000."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.research import router as research_router
from app.core.config import Settings, get_settings
from app.services.firecrawl import FirecrawlService
from app.services.feedback import FeedbackDelivery
from app.services.groq import GroqService
from app.services.repository import RepositoryError, SupabaseRepository
from app.services.tracing import WorkflowTracer
from app.services.worker import ResearchWorker
from app.workflows.research import ResearchWorkflow


def create_app(settings: Settings | None = None, *, repository: SupabaseRepository | None = None,
               workflow: ResearchWorkflow | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        repo = repository or SupabaseRepository(config)
        model = web = tracer = None
        try:
            graph = workflow
            if graph is None:
                model, web = GroqService(config), FirecrawlService(config)
                tracer = WorkflowTracer(config)
                graph = ResearchWorkflow(config, model, web, tracer)
            app.state.repository = repo
            worker = ResearchWorker(config, repo, graph)
            delivery = FeedbackDelivery(repo, tracer) if tracer else None
            app.state.worker = worker
            worker.start()
            if delivery:
                delivery.start()
            try:
                yield
            finally:
                await worker.stop()
                if delivery:
                    await delivery.stop()
        finally:
            if model:
                await model.aclose()
            if web:
                await web.aclose()
            if tracer:
                await asyncio.to_thread(tracer.flush)
            if repository is None:
                await repo.aclose()

    app = FastAPI(title="PitchPrep API", version="0.2.0", lifespan=lifespan)
    app.state.settings = config
    if repository is not None:
        app.state.repository = repository
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(config.frontend_origin).rstrip("/")],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID"],
    )
    app.include_router(health_router, prefix="/api")
    app.include_router(research_router, prefix="/api")

    @app.exception_handler(RepositoryError)
    async def repository_error(request: Request, error: RepositoryError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"error": error.code, "message": error.message})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "invalid_input",
                "details": [
                    {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
                    for item in error.errors()
                ],
            },
        )

    return app
