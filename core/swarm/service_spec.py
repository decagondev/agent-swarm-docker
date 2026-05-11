"""Pure-data DTO describing a Swarm service to be created.

Keeping this dataclass independent of `docker.types` lets `SwarmManager` be
tested with a `FakeDockerClient` Protocol-conforming stub.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ServiceSpec:
    image: str
    command: list[str]
    name: str
    labels: dict[str, str]
    env: dict[str, str] = field(default_factory=dict)
    mounts: list[str] = field(default_factory=list)
    restart_condition: str = "none"  # one of: none, on-failure, any

    def to_create_kwargs(self) -> dict[str, Any]:
        """Lower to the kwargs `docker.services.create()` expects."""
        return {
            "image": self.image,
            "command": list(self.command),
            "name": self.name,
            "labels": dict(self.labels),
            "env": [f"{k}={v}" for k, v in self.env.items()],
            "mounts": list(self.mounts),
            "restart_policy": {"Condition": self.restart_condition},
        }
