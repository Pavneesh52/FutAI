"""Live LLM tests using Grok (Phase 3).

Marked with `@pytest.mark.llm` and deselected by default during normal pytest runs.
Run with: `uv run pytest -m llm` (requires `GROK_API_KEY` to be set in environment or .env).
"""

from __future__ import annotations

import pytest
from app.agents.basic_agent import BasicAnalystAgent
from app.core.config import get_settings
from app.core.llm import LLMClient

from tests.unit.test_tools import StubMatchDataService


@pytest.fixture
def stub_service() -> StubMatchDataService:
    return StubMatchDataService()


@pytest.mark.llm
@pytest.mark.asyncio
async def test_live_grok_simple_stat(stub_service: StubMatchDataService) -> None:
    settings = get_settings()
    if not settings.resolved_llm_api_key:
        pytest.skip("GROQ_API_KEY / LLM_API_KEY is not set in environment or .env")

    llm = LLMClient(settings=settings)
    agent = BasicAnalystAgent(llm_client=llm)

    result = await agent.run(
        query="How many shots did Arsenal take in match 100?",
        match_id=100,
        service=stub_service,
    )

    assert result.query_type == "simple_stat"
    assert "16" in result.answer_markdown
    assert any("team_match_stats:100:1" in e.ref for e in result.evidence)


@pytest.mark.llm
@pytest.mark.asyncio
async def test_live_grok_player_stat(stub_service: StubMatchDataService) -> None:
    settings = get_settings()
    if not settings.resolved_llm_api_key:
        pytest.skip("GROQ_API_KEY / LLM_API_KEY is not set in environment or .env")

    llm = LLMClient(settings=settings)
    agent = BasicAnalystAgent(llm_client=llm)

    result = await agent.run(
        query="How many goals and assists did Bukayo Saka have in match 100?",
        match_id=100,
        service=stub_service,
    )

    assert result.query_type == "player"
    assert "1" in result.answer_markdown
    assert any("player_match_stats:100:10" in e.ref for e in result.evidence)


@pytest.mark.llm
@pytest.mark.asyncio
async def test_live_grok_tactical_ppda(stub_service: StubMatchDataService) -> None:
    settings = get_settings()
    if not settings.resolved_llm_api_key:
        pytest.skip("GROQ_API_KEY / LLM_API_KEY is not set in environment or .env")

    llm = LLMClient(settings=settings)
    agent = BasicAnalystAgent(llm_client=llm)

    result = await agent.run(
        query="Which team pressed more intensely in match 100, and what were their PPDA values?",
        match_id=100,
        service=stub_service,
    )

    assert result.query_type == "tactical"
    assert "8.2" in result.answer_markdown or "14.5" in result.answer_markdown
    assert len(result.evidence) >= 1
