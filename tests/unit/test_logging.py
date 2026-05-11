"""Tests for `SwarmEventLogger`."""

import io
import threading

from rich.console import Console

import agents  # noqa: F401 — populates REGISTRY
from core.io.shared_volume import SharedVolume
from core.logging import SwarmEventLogger
from core.registry import REGISTRY
from core.supervisor import SwarmAgentExecutor
from core.swarm import ResultWatcher, SwarmManager


def _capture_console() -> tuple[SwarmEventLogger, io.StringIO]:
    buf = io.StringIO()
    console = Console(file=buf, no_color=True, width=200)
    return SwarmEventLogger(console=console), buf


# ----- per-method emission --------------------------------------------------


def test_spawn_emits_label_agent_service_job():
    logger, buf = _capture_console()
    logger.spawn(agent="capitalize", job_id="job-7", service_id="svc-abcd1234")
    out = buf.getvalue()
    assert "SPAWN" in out
    assert "capitalize" in out
    assert "svc-abcd1234"[:12] in out
    assert "job-7" in out


def test_complete_emits_elapsed():
    logger, buf = _capture_console()
    logger.complete("reverse", "j", elapsed_s=1.234)
    assert "DONE" in buf.getvalue()
    assert "1.23s" in buf.getvalue()


def test_cleanup_emits_label():
    logger, buf = _capture_console()
    logger.cleanup("capitalize", "j", "svc-xx")
    assert "CLEAN" in buf.getvalue()


def test_reap_skips_when_zero():
    logger, buf = _capture_console()
    logger.reap(0)
    assert buf.getvalue() == ""


def test_reap_emits_when_nonzero():
    logger, buf = _capture_console()
    logger.reap(3)
    assert "REAP" in buf.getvalue()
    assert "3" in buf.getvalue()


def test_llm_round_emits_tool_count():
    logger, buf = _capture_console()
    logger.llm_round(iteration=2, n_tool_calls=4)
    assert "iter 2" in buf.getvalue()
    assert "tools=4" in buf.getvalue()


def test_llm_final_emits_char_count():
    logger, buf = _capture_console()
    logger.llm_final(iteration=3, length=123)
    assert "final answer" in buf.getvalue()
    assert "chars=123" in buf.getvalue()


def test_silent_logger_emits_nothing():
    logger = SwarmEventLogger.silent()
    # All methods must accept their normal args without printing anywhere.
    logger.spawn("a", "j", "s")
    logger.complete("a", "j", 0.1)
    logger.cleanup("a", "j", "s")
    logger.reap(5)
    logger.llm_round(0, 2)
    logger.llm_final(1, 42)
    # Nothing to assert — the absence of a console attribute means no I/O.
    assert logger._console is None


# ----- integration with SwarmAgentExecutor ----------------------------------


def test_executor_emits_spawn_done_clean_for_each_call(tmp_path, fake_docker):
    logger, buf = _capture_console()
    volume = SharedVolume(tmp_path)
    volume.ensure_dirs()
    manager = SwarmManager(client=fake_docker, image="img", logger=logger)
    watcher = ResultWatcher(volume.results_dir, poll_interval_s=0.01)
    executor = SwarmAgentExecutor(
        REGISTRY, volume, manager, watcher,
        agent_timeout_s=1.0, logger=logger,
    )

    # Background writer simulates the agent service producing a result file.
    import time

    def _writer():
        time.sleep(0.05)
        volume.result_path("j", "capitalize").write_text("OK")

    t = threading.Thread(target=_writer)
    t.start()
    try:
        executor.execute([("capitalize", "j")])
    finally:
        t.join()

    out = buf.getvalue()
    assert "SPAWN" in out and "DONE" in out and "CLEAN" in out
    assert "capitalize" in out
