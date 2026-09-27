"""Per-match aggregates.

Phase 1 fills the columns that are simple counts over events. The columns that need a
documented definition (``possession_pct``, ``ppda``, ``field_tilt``) and ``xa`` stay NULL
until Phase 2's ``docs/metrics.md`` and ``scripts/compute_stats.py``.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TeamMatchStats(Base):
    """Aggregated team performance in one match."""

    __tablename__ = "team_match_stats"
    __table_args__ = (
        UniqueConstraint("match_id", "team_id", name="uq_team_match_stats_match_id_team_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)

    possession_pct: Mapped[float | None] = mapped_column(Float)  # Phase 2
    xg: Mapped[float | None] = mapped_column(Float)
    shots: Mapped[int | None] = mapped_column(Integer)
    shots_on_target: Mapped[int | None] = mapped_column(Integer)
    passes: Mapped[int | None] = mapped_column(Integer)
    pass_accuracy: Mapped[float | None] = mapped_column(Float)
    ppda: Mapped[float | None] = mapped_column(Float)  # Phase 2
    field_tilt: Mapped[float | None] = mapped_column(Float)  # Phase 2
    formation: Mapped[str | None] = mapped_column(String(20))

    def __repr__(self) -> str:
        return f"TeamMatchStats(match_id={self.match_id}, team_id={self.team_id})"


class PlayerMatchStats(Base):
    """Aggregated player performance in one match."""

    __tablename__ = "player_match_stats"
    __table_args__ = (
        UniqueConstraint("match_id", "player_id", name="uq_player_match_stats_match_id_player_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)

    minutes_played: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    xg: Mapped[float | None] = mapped_column(Float)
    # StatsBomb open data has no xA (see IMPLEMENTATION.md section 6.1): stays NULL
    # unless docs/metrics.md documents a proxy.
    xa: Mapped[float | None] = mapped_column(Float)
    passes: Mapped[int | None] = mapped_column(Integer)
    pass_accuracy: Mapped[float | None] = mapped_column(Float)
    shots: Mapped[int | None] = mapped_column(Integer)
    tackles: Mapped[int | None] = mapped_column(Integer)
    position_played: Mapped[str | None] = mapped_column(String(80))

    def __repr__(self) -> str:
        return f"PlayerMatchStats(match_id={self.match_id}, player_id={self.player_id})"
