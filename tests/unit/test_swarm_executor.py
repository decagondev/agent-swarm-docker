"""Unit tests for `SwarmAgentExecutor` — uses FakeDockerClient + a real ResultWatcher.

The fake docker client doesn't actually run agents, so the test scaffolds the
result files itself (mid-spawn via a background thread) to simulate a real
agent writing its output to the shared volume.
"""

import threading
import time

import pytest

import agents  # noqa: F401 — populates REGISTRY
from core.io.shared_volume import SharedVolume
from core.registry import REGISTRY
from core.supervisor import SwarmAgentExecutor
from core.swarm import ResultWatcher, ResultWatcherTimeoutError, SwarmManager


@pytest.fixture
def volume(tmp_path):
    v = SharedVolume(tmp_path)
    v.ensure_dirs()
    return v


@pytest.fixture
def manager(fake_docker):
    return SwarmManager(client=fake_docker, image="img", poll_interval_s=0.01)


@pytest.fixture
def watcher(volume):
    return ResultWatcher(volume.results_dir, poll_interval_s=0.01)


@pytest.fixture
def executor(volume, manager, watcher):
    return SwarmAgentExecutor(
        registry=REGISTRY,
        volume=volume,
        swarm=manager,
        watcher=watcher,
        max_workers=4,
        agent_timeout_s=1.0,
    )


def _write_result_after(volume, job_id, agent, body, delay_s=0.05):
    """Background helper: write a fake result file mid-poll."""
    def _w():
        time.sleep(delay_s)
        volume.result_path(job_id, agent).write_text(body, encoding="utf-8")

    t = threading.Thread(target=_w)
    t.start()
    return t


def test_spawn_wait_cleanup_for_each_call(volume, manager, watcher, fake_docker, executor):
    threads = [
        _write_result_after(volume, "j", "capitalize", "HELLO"),
        _write_result_after(volume, "j", "reverse", "olleh"),
    ]
    try:
        results = executor.execute([("capitalize", "j"), ("reverse", "j")])
    finally:
        for t in threads:
            t.join()

    assert {r.agent_name for r in results} == {"capitalize", "reverse"}
    # services.create called exactly twice.
    assert len(fake_docker.services.create_calls) == 2
    # Both services were cleaned up.
    assert all(s.removed for s in fake_docker.services._services.values())


def test_agent_result_summary_is_file_content(volume, fake_docker, executor):
    t = _write_result_after(volume, "j", "capitalize", "PAYLOAD")
    try:
        [result] = executor.execute([("capitalize", "j")])
    finally:
        t.join()
    assert result.summary == "PAYLOAD"
    assert result.output_path.read_text() == "PAYLOAD"


def test_summary_clipped_when_oversized(volume, fake_docker, manager, watcher):
    body = "x" * 5000
    t = _write_result_after(volume, "j", "capitalize", body)
    ex = SwarmAgentExecutor(
        REGISTRY, volume, manager, watcher,
        agent_timeout_s=1.0, summary_clip_chars=100,
    )
    try:
        [result] = ex.execute([("capitalize", "j")])
    finally:
        t.join()
    assert len(result.summary) == 101  # 100 + ellipsis
    assert result.summary.endswith("…")


def test_cleanup_runs_even_on_watcher_timeout(volume, fake_docker, manager, watcher):
    ex = SwarmAgentExecutor(
        REGISTRY, volume, manager, watcher, agent_timeout_s=0.05
    )
    with pytest.raises(ResultWatcherTimeoutError):
        ex.execute([("capitalize", "j")])

    assert all(s.removed for s in fake_docker.services._services.values())


def test_unknown_agent_validated_up_front(volume, fake_docker, executor):
    with pytest.raises(KeyError):
        executor.execute([("no_such_agent", "j")])
    # No spawn happened.
    assert fake_docker.services.create_calls == []
