"""Stable response types for agent tools and operator workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ObservationStatus(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Artifact:
    path: str
    kind: str = "file"
    identifier: str | None = None

    def to_dict(self) -> dict[str, str]:
        result = {"path": self.path, "kind": self.kind}
        if self.identifier:
            result["id"] = self.identifier
        return result


@dataclass(frozen=True)
class Observation:
    status: ObservationStatus
    summary: str
    next_actions: tuple[str, ...] = ()
    artifacts: tuple[Artifact, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("Observation summary cannot be blank")
        if any(not action.strip() for action in self.next_actions):
            raise ValueError("Observation next actions cannot contain blank values")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "summary": self.summary,
            "next_actions": list(self.next_actions),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "details": self.details,
        }

