"""Analysis endpoints (IMPLEMENTATION.md section 6.4)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.basic_agent import BasicAnalystAgent
from app.api.deps import get_analyst_agent, get_match_data_service
from app.schemas.analysis import AnalysisRequest, AnalysisResult
from app.services.match_data import MatchDataService

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("", response_model=AnalysisResult)
async def analyze_query(
    body: AnalysisRequest,
    service: Annotated[MatchDataService, Depends(get_match_data_service)],
    agent: Annotated[BasicAnalystAgent, Depends(get_analyst_agent)],
) -> AnalysisResult:
    """Analyze a football question using deterministic tools and Grok."""
    if body.match_id is not None:
        # Validates match exists, raising MatchNotFoundError (HTTP 404) if not found
        await service.get_match(body.match_id)

    return await agent.run(
        query=body.query,
        match_id=body.match_id,
        service=service,
    )
