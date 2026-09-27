"""Tests for BasicAnalystAgent using a mock LLM client."""

from __future__ import annotations

import json
from typing import Any

import pytest
from app.agents.basic_agent import BasicAnalystAgent
from app.core.errors import ValidationFailedError
from app.core.llm import LLMClient, LLMResponse, ToolCall

from tests.unit.test_tools import StubMatchDataService


class MockLLMClient(LLMClient):
    """Mock LLM that returns scripted responses."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = list(responses)
        self.call_history: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_retries: int = 2,
    ) -> LLMResponse:
        self.call_history.append({"messages": messages, "tools": tools})
        if not self.responses:
            raise RuntimeError("MockLLMClient ran out of scripted responses")
        return self.responses.pop(0)


@pytest.fixture
def stub_service() -> StubMatchDataService:
    return StubMatchDataService()


@pytest.mark.asyncio
async def test_agent_tool_calling_loop_success(stub_service: StubMatchDataService) -> None:
    # 1. LLM requests get_match_stats
    # 2. LLM receives tool output and returns final JSON
    resp1 = LLMResponse(
        content=None,
        tool_calls=[ToolCall(id="call_1", name="get_match_stats", arguments={"match_id": 100})],
    )
    resp2 = LLMResponse(
        content=json.dumps(
            {
                "query_type": "simple_stat",
                "answer_markdown": "Arsenal scored 5 goals and took 16 shots in match 100.",
                "evidence": [
                    {"ref": "team_match_stats:100:1", "label": "Arsenal Shots", "value": 16}
                ],
                "confidence": 1.0,
            }
        )
    )

    mock_llm = MockLLMClient([resp1, resp2])
    agent = BasicAnalystAgent(llm_client=mock_llm)

    result = await agent.run(
        query="How many shots did Arsenal take in match 100?",
        match_id=100,
        service=stub_service,
    )

    assert result.query_type == "simple_stat"
    assert "Arsenal scored 5 goals" in result.answer_markdown
    assert len(result.evidence) == 1
    assert result.evidence[0].ref == "team_match_stats:100:1"
    assert result.confidence == 1.0
    assert len(mock_llm.call_history) == 2


@pytest.mark.asyncio
async def test_agent_iteration_cap_exceeded(stub_service: StubMatchDataService) -> None:
    # LLM keeps calling tools infinitely
    infinite_tool_calls = [
        LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(id=f"call_{i}", name="get_match_stats", arguments={"match_id": 100})
            ],
        )
        for i in range(10)
    ]

    mock_llm = MockLLMClient(infinite_tool_calls)
    agent = BasicAnalystAgent(llm_client=mock_llm, max_iterations=4)

    with pytest.raises(ValidationFailedError) as exc_info:
        await agent.run(query="What were the stats?", match_id=100, service=stub_service)

    assert "maximum iterations (4)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_agent_reformats_plain_text_to_json(stub_service: StubMatchDataService) -> None:
    # 1. LLM returns non-JSON text
    # 2. Agent asks to reformat
    # 3. LLM returns valid JSON
    resp1 = LLMResponse(content="Arsenal took 16 shots.")
    resp2 = LLMResponse(
        content=json.dumps(
            {
                "query_type": "simple_stat",
                "answer_markdown": "Arsenal took 16 shots in match 100.",
                "evidence": [{"ref": "team_match_stats:100:1", "label": "Shots", "value": 16}],
                "confidence": 1.0,
            }
        )
    )

    mock_llm = MockLLMClient([resp1, resp2])
    agent = BasicAnalystAgent(llm_client=mock_llm)

    result = await agent.run(
        query="How many shots did Arsenal take?", match_id=100, service=stub_service
    )
    assert result.query_type == "simple_stat"
    assert "Arsenal took 16 shots" in result.answer_markdown
    assert len(mock_llm.call_history) == 2
