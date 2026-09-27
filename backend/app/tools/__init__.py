"""Deterministic tool functions the LLM is allowed to call (Phase 3)."""

from __future__ import annotations

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
    PlayerMetricEnum,
    calculate_player_metric,
    find_player,
    find_team,
    get_player_stats,
)
from app.tools.registry import ToolDefinition, ToolRegistry, create_default_tool_registry

__all__ = [
    "CalculatePlayerMetricInput",
    "FindPlayerInput",
    "FindTeamInput",
    "GetMatchEventsInput",
    "GetMatchPlayersInput",
    "GetMatchStatsInput",
    "GetPlayerStatsInput",
    "GetTeamStatsInput",
    "PlayerMetricEnum",
    "ToolDefinition",
    "ToolRegistry",
    "calculate_player_metric",
    "create_default_tool_registry",
    "find_player",
    "find_team",
    "get_match_events",
    "get_match_players",
    "get_match_stats",
    "get_player_stats",
    "get_team_stats",
]
