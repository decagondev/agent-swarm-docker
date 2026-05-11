"""Tests for `SwarmManager` against a `FakeDockerClient`."""

import pytest

from core.swarm import (
    ServiceSpec,
    SpawnedService,
    SwarmManager,
    SwarmServiceError,
    SwarmTimeoutError,
)


@pytest.fixture
def manager(fake_docker):
    return SwarmManager(
        client=fake_docker,
        image="agent-swarm:test",
        shared_volume="my-volume",
        poll_interval_s=0.01,
    )


# ----- build_spec / spawn_agent ---------------------------------------------


def test_build_spec_constructs_runner_command(manager):
    spec = manager.build_spec("capitalize", "job-42")
    assert spec.image == "agent-swarm:test"
    assert spec.command == [
        "python",
        "-m",
        "agents.runner",
        "--agent",
        "capitalize",
        "--job",
        "job-42",
    ]


def test_build_spec_labels_carry_job_and_agent(manager):
    spec = manager.build_spec("reverse", "job-xyz")
    assert spec.labels["agent-swarm.job-id"] == "job-xyz"
    assert spec.labels["agent-swarm.agent"] == "reverse"
    assert spec.labels["agent-swarm.role"] == "ephemeral"


def test_build_spec_mounts_shared_volume(manager):
    spec = manager.build_spec("capitalize", "j")
    assert spec.mounts == ["my-volume:/app/data:rw"]


def test_build_spec_includes_data_root_env(manager):
    spec = manager.build_spec("capitalize", "j")
    assert spec.env["DATA_ROOT"] == "/app/data"


def test_build_spec_merges_extra_env(manager):
    spec = manager.build_spec("capitalize", "j", extra_env={"LLM_PROVIDER": "groq"})
    assert spec.env["LLM_PROVIDER"] == "groq"
    assert spec.env["DATA_ROOT"] == "/app/data"


def test_service_spec_to_create_kwargs_shape():
    spec = ServiceSpec(
        image="img",
        command=["cmd"],
        name="n",
        labels={"k": "v"},
        env={"A": "1"},
        mounts=["src:/dst"],
        restart_condition="none",
    )
    kw = spec.to_create_kwargs()
    assert kw["image"] == "img"
    assert kw["command"] == ["cmd"]
    assert kw["env"] == ["A=1"]
    assert kw["mounts"] == ["src:/dst"]
    assert kw["restart_policy"] == {"Condition": "none"}


def test_spawn_agent_calls_services_create(manager, fake_docker):
    spawned = manager.spawn_agent("reverse", "abc123")

    assert isinstance(spawned, SpawnedService)
    assert spawned.agent == "reverse"
    assert spawned.job_id == "abc123"
    assert spawned.service_id.startswith("svc-")

    assert len(fake_docker.services.create_calls) == 1
    call = fake_docker.services.create_calls[0]
    assert call["image"] == "agent-swarm:test"
    assert "reverse" in call["command"]
    assert "abc123" in call["command"]
    assert call["labels"]["agent-swarm.agent"] == "reverse"
    assert call["labels"]["agent-swarm.job-id"] == "abc123"


# ----- wait_for -------------------------------------------------------------


def test_wait_for_returns_exit_code_zero_on_complete(manager, fake_docker):
    spawned = manager.spawn_agent("capitalize", "j")
    svc = fake_docker.services.get(spawned.service_id)
    svc.set_tasks(
        [{"Status": {"State": "complete", "ContainerStatus": {"ExitCode": 0}}}]
    )
    assert manager.wait_for(spawned, timeout_s=1.0) == 0


def test_wait_for_returns_nonzero_exit_code_on_failed(manager, fake_docker):
    spawned = manager.spawn_agent("capitalize", "j")
    svc = fake_docker.services.get(spawned.service_id)
    svc.set_tasks(
        [{"Status": {"State": "failed", "ContainerStatus": {"ExitCode": 2}}}]
    )
    assert manager.wait_for(spawned, timeout_s=1.0) == 2


def test_wait_for_times_out(manager, fake_docker):
    spawned = manager.spawn_agent("capitalize", "j")
    svc = fake_docker.services.get(spawned.service_id)
    svc.set_tasks([{"Status": {"State": "running"}}])

    with pytest.raises(SwarmTimeoutError, match="running"):
        manager.wait_for(spawned, timeout_s=0.05)


def test_wait_for_raises_if_service_disappears(manager, fake_docker):
    spawned = manager.spawn_agent("capitalize", "j")
    del fake_docker.services._services[spawned.service_id]
    with pytest.raises(SwarmServiceError, match="disappeared"):
        manager.wait_for(spawned, timeout_s=1.0)


# ----- cleanup --------------------------------------------------------------


def test_cleanup_removes_service(manager, fake_docker):
    spawned = manager.spawn_agent("capitalize", "j")
    manager.cleanup(spawned)
    assert fake_docker.services.get(spawned.service_id).removed is True


def test_cleanup_idempotent_on_missing(manager):
    # Removing a non-existent service should not raise.
    ghost = SpawnedService(service_id="svc-missing", name="x", job_id="j", agent="a")
    manager.cleanup(ghost)  # no-op


# ----- list_active ----------------------------------------------------------


def test_list_active_returns_running_services(manager):
    manager.spawn_agent("capitalize", "j1")
    manager.spawn_agent("reverse", "j1")

    active = manager.list_active({"agent-swarm.job-id": "j1"})
    assert {s.agent for s in active} == {"capitalize", "reverse"}


def test_list_active_excludes_removed(manager):
    s1 = manager.spawn_agent("capitalize", "j2")
    manager.spawn_agent("reverse", "j2")
    manager.cleanup(s1)
    active = manager.list_active({"agent-swarm.job-id": "j2"})
    assert [s.agent for s in active] == ["reverse"]
