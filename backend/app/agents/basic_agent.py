"""Single tool-calling analyst agent (Phase 3).

Loop: LLM call -> if tool_calls, execute tools -> feed results -> repeat until final JSON.
Strictly enforces Rule R1 (no invented stats), R2 (typed tools only), R3 (Pydantic validation).
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.core.errors import AppError, ValidationFailedError
from app.core.llm import LLMClient
from app.core.logging import get_logger
from app.schemas.analysis import AnalysisResult, EvidenceItem
from app.services.match_data import MatchDataService
from app.tools.registry import ToolRegistry, create_default_tool_registry

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an expert AI Football Match Analyst. Provide accurate, data-grounded analysis using only the provided tools.

RULES:
1. ONLY state numbers from tool results. NEVER guess or invent stats.
2. Resolve names with find_player/find_team before calling stat tools.
3. If data is unavailable, say so clearly.
4. Copy EXACT ref strings from tool evidence_refs in your evidence list.
5. For player questions, use get_match_players to see all players in a match.

OUTPUT: When done gathering data, respond with ONLY this JSON:
{"query_type": "simple_stat"|"player"|"tactical"|"comparison"|"report",
 "answer_markdown": "<markdown answer citing tool numbers>",
 "evidence": [{"ref": "<exact ref from tool>", "label": "<description>", "value": <number or string>}],
 "confidence": <0.0-1.0>}
"""


class AgentOutputSchema(BaseModel):
    """Pydantic model for the agent's final JSON response."""

    query_type: Literal["simple_stat", "player", "tactical", "comparison", "report"] = (
        "simple_stat"
    )
    answer_markdown: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


def _extract_json_block(text: str) -> dict[str, Any] | None:
    """Extract JSON object from text, handling optional markdown code fences."""
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return None


class BasicAnalystAgent:
    """Single-agent tool caller that answers questions by querying deterministic tools."""

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry | None = None,
        max_iterations: int = 6,
    ) -> None:
        self.llm = llm_client
        self.tools = tool_registry or create_default_tool_registry()
        self.max_iterations = max_iterations

    async def run(
        self,
        query: str,
        match_id: int | None = None,
        service: MatchDataService | None = None,
    ) -> AnalysisResult:
        """Execute the tool-calling loop until a validated answer is produced."""
        if service is None:
            raise AppError("MatchDataService must be provided to run the agent.")

        run_id = str(uuid.uuid4())
        tool_schemas = self.tools.get_openai_tool_schemas()

        # Provide formal schema for models that use tool calling for final structured output
        final_schema = {
            "type": "function",
            "function": {
                "name": "submit_final_analysis",
                "description": "Submit the final structured football analysis once all data has been gathered from tools.",
                "parameters": AgentOutputSchema.model_json_schema(),
            },
        }
        json_schema_alias = {
            "type": "function",
            "function": {
                "name": "json",
                "description": "Output final structured JSON response matching the analysis schema.",
                "parameters": AgentOutputSchema.model_json_schema(),
            },
        }
        tool_schemas.extend([final_schema, json_schema_alias])

        user_content = query
        if match_id is not None:
            user_content = f"Context Match ID: {match_id}\n\nUser Question: {query}"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        collected_evidence_refs: list[str] = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            logger.info("agent_loop_iteration iteration=%d/%d", iteration, self.max_iterations)

            response = await self.llm.complete(
                messages=messages,
                tools=tool_schemas,
            )

            if response.has_tool_calls:
                # Check if model returned final JSON inside a pseudo tool call (e.g. 'json' or 'submit')
                for tc in response.tool_calls:
                    if (
                        tc.name in ("json", "final_answer", "submit_analysis", "AgentOutputSchema")
                        or tc.name not in self.tools._tools
                    ) and isinstance(tc.arguments, dict) and "answer_markdown" in tc.arguments:
                        try:
                            agent_output = AgentOutputSchema.model_validate(tc.arguments)
                            return AnalysisResult(
                                run_id=run_id,
                                query_type=agent_output.query_type,
                                answer_markdown=agent_output.answer_markdown,
                                evidence=agent_output.evidence,
                                sources=[],
                                confidence=agent_output.confidence,
                                degraded=False,
                                retry_count=0,
                            )
                        except ValidationError:
                            pass

                tool_calls_payload = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ]
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": tool_calls_payload,
                    }
                )

                for tc in response.tool_calls:
                    try:
                        tool_result = await self.tools.execute(
                            name=tc.name,
                            arguments=tc.arguments,
                            service=service,
                        )
                        collected_evidence_refs.extend(tool_result.evidence_refs)
                        content_str = json.dumps(
                            {
                                "data": tool_result.data,
                                "evidence_refs": tool_result.evidence_refs,
                            }
                        )
                    except Exception as exc:
                        logger.warning(
                            "tool_failed tool=%s err=%s",
                            tc.name,
                            exc,
                        )
                        content_str = json.dumps({"error": str(exc)})

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": tc.name,
                            "content": content_str,
                        }
                    )
                continue

            raw_content = response.content or ""
            parsed_json = _extract_json_block(raw_content)

            if parsed_json is not None:
                try:
                    agent_output = AgentOutputSchema.model_validate(parsed_json)
                    return AnalysisResult(
                        run_id=run_id,
                        query_type=agent_output.query_type,
                        answer_markdown=agent_output.answer_markdown,
                        evidence=agent_output.evidence,
                        sources=[],
                        confidence=agent_output.confidence,
                        degraded=False,
                        retry_count=0,
                    )
                except ValidationError as val_err:
                    logger.warning("agent_output_schema_validation_failed err=%s", val_err)
            else:
                logger.warning("agent_output_not_json raw=%r", raw_content[:200])

            if iteration < self.max_iterations:
                messages.append({"role": "assistant", "content": raw_content})
                format_msg = (
                    "Please output ONLY valid JSON matching schema:\n"
                    '{"query_type": "simple_stat"|"player"|"tactical"|"comparison", '
                    '"answer_markdown": "...", "evidence": [{"ref": "...", "label": "...", '
                    '"value": ...}], "confidence": 1.0}'
                )
                messages.append(
                    {
                        "role": "user",
                        "content": format_msg,
                    }
                )
                continue

        raise ValidationFailedError(
            f"Agent reached maximum iterations ({self.max_iterations}) without structured answer.",
            context={"run_id": run_id, "iterations": iteration},
        )
