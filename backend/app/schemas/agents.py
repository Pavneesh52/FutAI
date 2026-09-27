"""Agent findings and critic contracts (IMPLEMENTATION.md section 6.2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AgentFinding(BaseModel):
    """Structured finding returned by an agent, referencing evidence pointers."""

    agent: str
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)


class CriticIssue(BaseModel):
    """A specific flaw identified during reflection/critic evaluation."""

    type: Literal["unsupported_claim", "contradiction", "hallucination", "missing_evidence"]
    claim: str
    reason: str


class CriticResult(BaseModel):
    """Outcome of critic evaluation."""

    passed: bool
    issues: list[CriticIssue] = Field(default_factory=list)
    required_action: Literal["retrieve_more_data", "redo_tactical", "redo_player", "none"]
