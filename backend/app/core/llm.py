"""Grok (xAI) LLM client wrapper (Phase 3).

Rule R4 (timeouts), error normalization into `LLMError`/`LLMTimeoutError`, token usage tracking,
and bounded retries with exponential backoff.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import openai
from openai import AsyncOpenAI

from app.core.config import Settings, get_settings
from app.core.errors import LLMError, LLMTimeoutError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Normalized response from an LLM completion call."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @property
    def has_tool_calls(self) -> bool:
        """True if the model requested one or more tool executions."""
        return len(self.tool_calls) > 0


class LLMClient:
    """Async client for Llama 3.3 70B (via Groq / OpenAI API) with retries and timeout."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model = self.settings.llm_model or "llama-3.3-70b-versatile"
        self.timeout = self.settings.llm_timeout_seconds

        self._client: AsyncOpenAI | None
        if client is not None:
            self._client = client
        elif self.settings.resolved_llm_api_key:
            self._client = AsyncOpenAI(
                api_key=self.settings.resolved_llm_api_key,
                base_url=self.settings.llm_base_url,
                timeout=self.timeout,
            )
        else:
            self._client = None

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_retries: int = 2,
    ) -> LLMResponse:
        """Send a completion request to the LLM with bounded retries and timeout enforcement."""
        if self._client is None:
            raise LLMError(
                "LLM API key is not configured. Set GROQ_API_KEY in your environment or .env.",
                context={"model": self.model},
            )

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice

        attempt = 0
        backoff_delay = 0.5

        while True:
            attempt += 1
            try:
                async with asyncio.timeout(self.timeout):
                    raw = await self._client.chat.completions.create(**kwargs)

                choice = raw.choices[0]
                message = choice.message

                parsed_tool_calls: list[ToolCall] = []
                if message.tool_calls:
                    for tc in message.tool_calls:
                        args_dict: dict[str, Any] = {}
                        if tc.function.arguments:
                            try:
                                args_dict = json.loads(tc.function.arguments)
                            except Exception as parse_err:
                                logger.warning(
                                    "failed_parsing_tool_call_args tool=%s err=%s",
                                    tc.function.name,
                                    parse_err,
                                )
                                args_dict = {}
                        parsed_tool_calls.append(
                            ToolCall(
                                id=tc.id,
                                name=tc.function.name,
                                arguments=args_dict,
                            )
                        )

                prompt_tokens = raw.usage.prompt_tokens if raw.usage else 0
                completion_tokens = raw.usage.completion_tokens if raw.usage else 0
                total_tokens = raw.usage.total_tokens if raw.usage else 0

                logger.info(
                    "llm_completion model=%s prompt=%d completion=%d tool_calls=%d",
                    self.model,
                    prompt_tokens,
                    completion_tokens,
                    len(parsed_tool_calls),
                )

                return LLMResponse(
                    content=message.content,
                    tool_calls=parsed_tool_calls,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )

            except (TimeoutError, openai.APITimeoutError) as exc:
                logger.warning("llm_call_timeout model=%s timeout=%.1f", self.model, self.timeout)
                raise LLMTimeoutError(
                    f"LLM request timed out after {self.timeout}s.",
                    context={"model": self.model, "timeout": self.timeout},
                ) from exc

            except (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.InternalServerError,
            ) as exc:
                if attempt <= max_retries:
                    logger.warning(
                        "llm_transient_error_retry attempt=%d/%d err=%s",
                        attempt,
                        max_retries,
                        exc,
                    )
                    await asyncio.sleep(backoff_delay)
                    backoff_delay *= 2.0
                    continue
                logger.error("llm_retries_exhausted model=%s err=%s", self.model, exc)
                raise LLMError(
                    f"LLM provider error after {max_retries} retries: {exc}",
                    context={"model": self.model, "attempts": attempt},
                ) from exc

            except openai.APIError as exc:
                logger.error("llm_api_error model=%s err=%s", self.model, exc)
                raise LLMError(
                    f"LLM API returned an error: {exc.message if hasattr(exc, 'message') else exc}",
                    context={"model": self.model, "status_code": getattr(exc, "status_code", None)},
                ) from exc

            except Exception as exc:
                logger.exception("llm_unexpected_error model=%s", self.model)
                raise LLMError(
                    f"Unexpected error during LLM call: {exc}",
                    context={"model": self.model},
                ) from exc
