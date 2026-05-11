"""Tests for `SwarmManager.reap_stale()` + startup hook."""

import pytest

from core.swarm import SwarmManager


def _seed_service(fake_docker, name: str, labels: dict[str, str]) -> None:
    """Inject a pre-existing service into the fake daemon."""
    fake_docker.services.create(name=name, labels=labels, command=["x"], image="img")


def test_startup_reaps_two_stale_ephemeral_services(fake_docker):
    _seed_service(fake_docker, "stale-1", {"agent-swarm.role": "ephemeral"})
    _seed_service(fake_docker, "stale-2", {"agent-swarm.role": "ephemeral"})

    SwarmManager(client=fake_docker)

    # Both stale services were removed.
    assert all(s.removed for s in fake_docker.services._services.values())


def test_startup_preserves_non_ephemeral_services(fake_docker):
    _seed_service(fake_docker, "supervisor", {"agent-swarm.role": "supervisor"})
    _seed_service(fake_docker, "stale", {"agent-swarm.role": "ephemeral"})

    SwarmManager(client=fake_docker)

    surviving = {s.name: s for s in fake_docker.services._services.values()}
    assert surviving["supervisor"].removed is False
    assert surviving["stale"].removed is True


def test_reap_stale_returns_count(fake_docker):
    _seed_service(fake_docker, "stale-1", {"agent-swarm.role": "ephemeral"})
    _seed_service(fake_docker, "stale-2", {"agent-swarm.role": "ephemeral"})
    _seed_service(fake_docker, "stale-3", {"agent-swarm.role": "ephemeral"})

    manager = SwarmManager(client=fake_docker, reap_stale_on_startup=False)
    count = manager.reap_stale()

    assert count == 3


def test_reap_stale_is_idempotent(fake_docker):
    _seed_service(fake_docker, "stale", {"agent-swarm.role": "ephemeral"})

    manager = SwarmManager(client=fake_docker)  # First reap happens here.
    # Second call should be a no-op (no live ephemeral services left).
    assert manager.reap_stale() == 0


def test_reap_stale_on_startup_false_skips_reap(fake_docker):
    _seed_service(fake_docker, "stale", {"agent-swarm.role": "ephemeral"})

    SwarmManager(client=fake_docker, reap_stale_on_startup=False)

    survivor = next(iter(fake_docker.services._services.values()))
    assert survivor.removed is False


def test_reap_stale_only_targets_own_label_prefix(fake_docker):
    """A different deployment using a different label_prefix should be untouched."""
    _seed_service(fake_docker, "other-tool", {"other.role": "ephemeral"})

    SwarmManager(client=fake_docker)

    only = next(iter(fake_docker.services._services.values()))
    assert only.removed is False


@pytest.fixture
def manager_with_seeded(fake_docker):
    return SwarmManager(client=fake_docker, poll_interval_s=0.01)


def test_subsequent_spawn_works_after_reap(manager_with_seeded, fake_docker):
    spawned = manager_with_seeded.spawn_agent("capitalize", "j1")
    assert spawned.service_id in fake_docker.services._services
