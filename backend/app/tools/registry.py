"""Tool registry mapping names to functions and Grok/OpenAI JSON schemas (Phase 3).

Rule R2 (deterministic tools), Rule R3 (Pydantic validation), Rule R8 (unit-testable without LLM).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.errors import ToolExecutionError, ValidationFailedError
from app.core.logging import get_logger
from app.schemas.tools import ToolResult
from app.services.match_data import MatchDataService
from app.tools.match_tools import (
    GetMatchEventsInput,
    GetMatchPlayersInput,
    GetMatchStatsInput,
    GetTeamStatsInput,
    get_match_events,
    get_match_players,
    get_match_stats,
    get_team_stats,
)
from app.tools.player_tools import (
    CalculatePlayerMetricInput,
    FindPlayerInput,
    FindTeamInput,
    GetPlayerStatsInput,
    calculate_player_metric,
    find_player,
    find_team,
    get_player_stats,
)

logger = get_logger(__name__)

ToolHandler = Callable[..., Awaitable[ToolResult]]


@dataclass
class ToolDefinition:
    """Registered tool metadata and execution handler."""

    name: str
    description: str
    input_model: type[BaseModel]
    handler: ToolHandler

    def to_openai_schema(self) -> dict[str, Any]:
        """Format the tool definition for Grok / OpenAI function calling."""
        schema = self.input_model.model_json_schema()
        defs = schema.pop("$defs", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Resolve $ref pointers inline — Groq / many OpenAI-compatible
        # providers reject JSON-Schema $defs/$ref.
        resolved_props = _resolve_refs(properties, defs)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": resolved_props,
                    "required": required,
                },
            },
        }


def _resolve_refs(obj: Any, defs: dict[str, Any]) -> Any:
    """Recursively replace ``{"$ref": "#/$defs/Foo"}`` with the actual definition."""
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref_path = obj["$ref"]  # e.g. "#/$defs/PlayerMetricEnum"
            ref_name = ref_path.rsplit("/", 1)[-1]
            resolved = defs.get(ref_name, obj)
            # The resolved value may itself contain $ref, recurse.
            return _resolve_refs(resolved, defs)
        return {k: _resolve_refs(v, defs) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(item, defs) for item in obj]
    return obj


class ToolRegistry:
    """Central registry of deterministic tools available to agents."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        input_model: type[BaseModel],
        handler: ToolHandler,
    ) -> None:
        """Register a new typed tool."""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            input_model=input_model,
            handler=handler,
        )

    def get_definitions(self) -> list[ToolDefinition]:
        """Return all registered tool definitions."""
        return list(self._tools.values())

    def get_openai_tool_schemas(self) -> list[dict[str, Any]]:
        """Return tool definitions in Grok/OpenAI tool format."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        service: MatchDataService,
    ) -> ToolResult:
        """Validate input arguments and execute the tool."""
        tool = self._tools.get(name)
        if tool is None:
            logger.warning("unknown_tool_requested tool=%s", name)
            raise ToolExecutionError(
                f"Tool '{name}' is not registered in the tool registry.",
                context={"tool_name": name},
            )

        try:
            validated_input = tool.input_model.model_validate(arguments)
        except ValidationError as exc:
            logger.warning("tool_input_validation_failed tool=%s err=%s", name, exc)
            raise ValidationFailedError(
                f"Invalid arguments for tool '{name}': {exc}",
                context={"tool_name": name, "errors": exc.errors()},
            ) from exc

        try:
            logger.info("executing_tool tool=%s", name)
            result = await tool.handler(service=service, **validated_input.model_dump())
            return result
        except Exception as exc:
            logger.exception("tool_execution_failed tool=%s", name)
            raise ToolExecutionError(
                f"Error executing tool '{name}': {exc}",
                context={"tool_name": name},
            ) from exc


def create_default_tool_registry() -> ToolRegistry:
    """Create and configure the default tool registry for the AI analyst."""
    registry = ToolRegistry()

    registry.register(
        name="get_match_stats",
        description=(
            "Fetch match overview and aggregate stats for both teams in a match (xG, shots, "
            "possession %, passes, pass accuracy %, PPDA, field tilt, formation)."
        ),
        input_model=GetMatchStatsInput,
        handler=get_match_stats,
    )

    registry.register(
        name="get_match_events",
        description=(
            "Fetch events for a match with minute, second, type, team, coordinates, and shot xG. "
            "Supports optional event_type filter (e.g. 'shot', 'pass', 'tackle', 'goal')."
        ),
        input_model=GetMatchEventsInput,
        handler=get_match_events,
    )

    registry.register(
        name="get_team_stats",
        description="Fetch statistics for a specific team, optionally for a specific match.",
        input_model=GetTeamStatsInput,
        handler=get_team_stats,
    )

    registry.register(
        name="get_match_players",
        description=(
            "Fetch per-player statistics for ALL players in a match (goals, assists, xG, passes, "
            "pass accuracy, shots, tackles, minutes played, position). Use this to compare players "
            "or find the best performer in a match."
        ),
        input_model=GetMatchPlayersInput,
        handler=get_match_players,
    )

    registry.register(
        name="get_player_stats",
        description="Fetch player stats for a specific player ID, optionally scoped to a match ID.",
        input_model=GetPlayerStatsInput,
        handler=get_player_stats,
    )

    registry.register(
        name="find_player",
        description=(
            "Resolve a player's natural name to candidate IDs and teams. "
            "Always use this when given a player name before querying player statistics."
        ),
        input_model=FindPlayerInput,
        handler=find_player,
    )

    registry.register(
        name="find_team",
        description=(
            "Resolve a team's natural name to candidate team IDs and countries. "
            "Always use this when given a team name before querying team statistics."
        ),
        input_model=FindTeamInput,
        handler=find_team,
    )

    registry.register(
        name="calculate_player_metric",
        description=(
            "Calculate or retrieve a specific metric for a player ID (e.g. goals, assists, xg, xa, "
            "passes, pass_accuracy, shots, tackles, minutes_played), optionally scoped to a match."
        ),
        input_model=CalculatePlayerMetricInput,
        handler=calculate_player_metric,
    )

    return registry
