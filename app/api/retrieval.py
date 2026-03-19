"""Internal retrieval endpoint for the thin pipeline."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings, get_mem0_adapter
from app.config import Settings
from app.schemas.api import RetrievalResponse
from app.schemas.events import RetrievalRequest
from app.services.retrieval import retrieve_context

router = APIRouter(prefix="/internal", tags=["retrieval"])


@router.post("/retrieval", response_model=RetrievalResponse)
def post_retrieval(
    retrieval_request: RetrievalRequest,
    settings: Settings = Depends(get_app_settings),
    mem0_adapter=Depends(get_mem0_adapter),
) -> RetrievalResponse:
    result = retrieve_context(
        settings,
        mem0_adapter,
        query=retrieval_request.query,
        scope=retrieval_request.scope.model_dump(),
    )
    return RetrievalResponse(**result)

