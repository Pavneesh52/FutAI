"""SQLAlchemy ORM models.

Every model must be imported here, or ``Base.metadata`` is incomplete and Alembic
autogenerate will happily drop tables it cannot see.
"""

from __future__ import annotations

from app.models.base import SOURCE_PREFIX, Base
from app.models.event import Event
from app.models.formation import Formation
from app.models.match import Match, Player, Team
from app.models.stats import PlayerMatchStats, TeamMatchStats

__all__ = [
    "SOURCE_PREFIX",
    "Base",
    "Event",
    "Formation",
    "Match",
    "Player",
    "PlayerMatchStats",
    "Team",
    "TeamMatchStats",
]
