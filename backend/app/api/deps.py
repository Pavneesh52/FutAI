"""FastAPI dependencies.

Routers depend on `MatchDataService`, `LLMClient`, `ToolRegistry`, and `BasicAnalystAgent`,
so tests can override single dependencies with in-memory stubs or mock clients.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.basic_agent import BasicAnalystAgent
from app.core.config import Settings, get_settings
from app.core.db import get_session_factory
from app.core.llm import LLMClient
from app.services.match_data import MatchDataService, PostgresMatchDataService
from app.tools.registry import ToolRegistry, create_default_tool_registry


async def get_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[AsyncSession]:
    """Yield one database session per request."""
    factory = get_session_factory(settings)
    async with factory() as session:
        yield session


def get_match_data_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MatchDataService:
    """The data source the routers and tools read from."""
    return PostgresMatchDataService(session)


def get_tool_registry() -> ToolRegistry:
    """Return the default registered deterministic tools."""
    return create_default_tool_registry()


def get_llm_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMClient:
    """Return an async Grok LLM client."""
    return LLMClient(settings=settings)


def get_analyst_agent(
    llm: Annotated[LLMClient, Depends(get_llm_client)],
    tools: Annotated[ToolRegistry, Depends(get_tool_registry)],
) -> BasicAnalystAgent:
    """Return the single tool-calling basic analyst agent."""
    return BasicAnalystAgent(llm_client=llm, tool_registry=tools)
