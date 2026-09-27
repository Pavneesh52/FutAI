"""API tests for POST /analysis endpoint."""

from __future__ import annotations

import json
from typing import Any

import pytest
from app.agents.basic_agent import BasicAnalystAgent
from app.api.deps import get_analyst_agent, get_match_data_service
from app.core.errors import LLMError, LLMTimeoutError
from app.core.llm import LLMClient, LLMResponse

from tests.conftest import build_app, build_client, offline_settings
from tests.unit.test_tools import StubMatchDataService


class MockLLM(LLMClient):
    """Mock LLM client for API tests."""

    def __init__(self, response: LLMResponse | Exception) -> None:
        self.response = response

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_retries: int = 2,
    ) -> LLMResponse:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.asyncio
async def test_post_analysis_success() -> None:
    settings = offline_settings()
    stub_service = StubMatchDataService()

    success_resp = LLMResponse(
        content=json.dumps(
            {
                "query_type": "simple_stat",
                "answer_markdown": "Arsenal took 16 shots and won 5-0.",
                "evidence": [{"ref": "team_match_stats:100:1", "label": "Shots", "value": 16}],
                "confidence": 1.0,
            }
        )
    )
    mock_agent = BasicAnalystAgent(llm_client=MockLLM(success_resp))

    app = build_app(settings)
    app.dependency_overrides[get_match_data_service] = lambda: stub_service
    app.dependency_overrides[get_analyst_agent] = lambda: mock_agent

    async with build_client(app) as client:
        res = await client.post(
            "/analysis", json={"query": "How many shots did Arsenal take?", "match_id": 100}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["query_type"] == "simple_stat"
        assert "Arsenal took 16 shots" in data["answer_markdown"]
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["ref"] == "team_match_stats:100:1"


@pytest.mark.asyncio
async def test_post_analysis_match_not_found() -> None:
    settings = offline_settings()
    stub_service = StubMatchDataService()
    mock_agent = BasicAnalystAgent(llm_client=MockLLM(LLMResponse(content="{}")))

    app = build_app(settings)
    app.dependency_overrides[get_match_data_service] = lambda: stub_service
    app.dependency_overrides[get_analyst_agent] = lambda: mock_agent

    async with build_client(app) as client:
        res = await client.post(
            "/analysis", json={"query": "Tell me about this match", "match_id": 999999}
        )
        assert res.status_code == 404
        data = res.json()
        assert data["error"]["code"] == "match_not_found"
        assert "999999" in data["error"]["message"]


@pytest.mark.asyncio
async def test_post_analysis_llm_timeout() -> None:
    settings = offline_settings()
    stub_service = StubMatchDataService()
    timeout_err = LLMTimeoutError("LLM request timed out after 45.0s.", context={"timeout": 45.0})
    mock_agent = BasicAnalystAgent(llm_client=MockLLM(timeout_err))

    app = build_app(settings)
    app.dependency_overrides[get_match_data_service] = lambda: stub_service
    app.dependency_overrides[get_analyst_agent] = lambda: mock_agent

    async with build_client(app) as client:
        res = await client.post("/analysis", json={"query": "Analyze tactics", "match_id": 100})
        assert res.status_code == 504
        data = res.json()
        assert data["error"]["code"] == "llm_timeout"


@pytest.mark.asyncio
async def test_post_analysis_llm_error() -> None:
    settings = offline_settings()
    stub_service = StubMatchDataService()
    provider_err = LLMError("Grok API key is not configured.", context={"model": "grok-2-latest"})
    mock_agent = BasicAnalystAgent(llm_client=MockLLM(provider_err))

    app = build_app(settings)
    app.dependency_overrides[get_match_data_service] = lambda: stub_service
    app.dependency_overrides[get_analyst_agent] = lambda: mock_agent

    async with build_client(app) as client:
        res = await client.post("/analysis", json={"query": "Analyze tactics", "match_id": 100})
        assert res.status_code == 502
        data = res.json()
        assert data["error"]["code"] == "llm_error"
