"""Formations used by a team during a match.

Sourced from StatsBomb's ``Starting XI`` and ``Tactical Shift`` tactics events, so a
match can hold several rows per team (a formation change creates another one).
"""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Formation(Base):
    """One formation used by one team for a stretch of a match."""

    __tablename__ = "formations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    # Rendered form of StatsBomb's integer formation, e.g. 442 -> "4-4-2".
    formation_string: Mapped[str] = mapped_column(String(20), nullable=False)
    period: Mapped[int] = mapped_column(Integer, nullable=False)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return (
            f"Formation(match_id={self.match_id}, team_id={self.team_id}, "
            f"formation={self.formation_string!r}, period={self.period})"
        )
