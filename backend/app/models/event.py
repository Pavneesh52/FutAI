"""Match events.

Note on identity: StatsBomb event v4.0.0 identifies events with **UUID strings**, so
``source_id`` holds that UUID and ``id`` is our own surrogate integer. ``related_event_id``
points at our surrogate id, resolved after insert (see the ETL).
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.match import Match


class Event(Base):
    """A single on-the-ball or off-the-ball event."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source_id", name="uq_events_source_id"),
        Index("ix_events_match_id_minute", "match_id", "minute"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    minute: Mapped[int] = mapped_column(Integer, nullable=False)
    second: Mapped[int] = mapped_column(Integer, nullable=False)
    # Normalised StatsBomb type, e.g. "pass", "shot", "tackle", "ball_receipt".
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    # Pitch is 120x80, coordinates from the acting team's perspective. NULL where the
    # source has no location (e.g. Half Start, some administrative events).
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    # Type-specific outcome name. Passes are stored as "Complete" when the source
    # omits an outcome, so pass accuracy never has to guess.
    outcome: Mapped[str | None] = mapped_column(String(60))
    xg: Mapped[float | None] = mapped_column(Float)
    related_event_id: Mapped[int | None] = mapped_column(BigInteger)
    possession_id: Mapped[int | None] = mapped_column(Integer)
    # For substitution events: the player who came ON (player_id is the one going OFF).
    replacement_player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"), nullable=True
    )
    source_id: Mapped[str] = mapped_column(String(120), nullable=False)

    match: Mapped[Match] = relationship()

    def __repr__(self) -> str:
        return (
            f"Event(id={self.id}, type={self.event_type!r}, "
            f"minute={self.minute}, source_id={self.source_id!r})"
        )
