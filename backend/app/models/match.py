"""Teams, players and matches (Appendix A of IMPLEMENTATION.md)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Team(Base):
    """A club or national team."""

    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("source_id", name="uq_teams_source_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(100))
    # Not present in StatsBomb open data; kept because the schema is final (Appendix A).
    founded_year: Mapped[int | None] = mapped_column(Integer)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False)

    players: Mapped[list[Player]] = relationship(back_populates="team")

    def __repr__(self) -> str:
        return f"Team(id={self.id}, name={self.name!r})"


class Player(Base):
    """A player.

    StatsBomb open data has no date of birth, and only tells us which team a player
    turned out for in a given match -- so ``birth_date`` stays NULL and ``team_id``
    records the team they appeared for.
    """

    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("source_id", name="uq_players_source_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    position: Mapped[str | None] = mapped_column(String(80))
    birth_date: Mapped[date | None] = mapped_column(Date)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False)

    team: Mapped[Team | None] = relationship(back_populates="players")

    def __repr__(self) -> str:
        return f"Player(id={self.id}, name={self.name!r})"


class Match(Base):
    """A single match."""

    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("source_id", name="uq_matches_source_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    competition: Mapped[str] = mapped_column(String(120), nullable=False)
    season: Mapped[str] = mapped_column(String(40), nullable=False)
    match_date: Mapped[date] = mapped_column(Date, nullable=False)
    # NULL means "not played / no score in the source", not zero.
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False)

    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])

    def __repr__(self) -> str:
        return f"Match(id={self.id}, date={self.match_date}, source_id={self.source_id!r})"
