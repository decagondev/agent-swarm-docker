"""Tests for `ResultWatcher`."""

import threading
import time

import pytest

from core.swarm import ResultWatcher, ResultWatcherTimeoutError


@pytest.fixture
def results_dir(tmp_path):
    d = tmp_path / "results"
    d.mkdir()
    return d


def test_returns_path_immediately_when_file_exists(results_dir):
    path = results_dir / "j__capitalize.result"
    path.write_text("HELLO")

    watcher = ResultWatcher(results_dir, poll_interval_s=0.01)
    assert watcher.wait_for("j", "capitalize", timeout_s=1.0) == path


def test_picks_up_file_written_mid_poll(results_dir):
    watcher = ResultWatcher(results_dir, poll_interval_s=0.01)
    target = results_dir / "j__capitalize.result"

    def _writer():
        time.sleep(0.05)
        target.write_text("LATE")

    t = threading.Thread(target=_writer)
    t.start()
    try:
        path = watcher.wait_for("j", "capitalize", timeout_s=1.0)
        assert path.read_text() == "LATE"
    finally:
        t.join()


def test_raises_on_timeout(results_dir):
    watcher = ResultWatcher(results_dir, poll_interval_s=0.01)
    with pytest.raises(ResultWatcherTimeoutError, match="did not appear"):
        watcher.wait_for("j", "capitalize", timeout_s=0.05)


def test_wait_for_many_returns_when_all_present(results_dir):
    (results_dir / "j__a.result").write_text("A")
    (results_dir / "j__b.result").write_text("B")
    (results_dir / "j__c.result").write_text("C")

    watcher = ResultWatcher(results_dir, poll_interval_s=0.01)
    found = watcher.wait_for_many("j", ["a", "b", "c"], timeout_s=1.0)

    assert set(found) == {"a", "b", "c"}
    assert found["a"].read_text() == "A"


def test_wait_for_many_picks_up_stragglers(results_dir):
    watcher = ResultWatcher(results_dir, poll_interval_s=0.01)
    (results_dir / "j__a.result").write_text("A")  # already there

    def _writer():
        time.sleep(0.05)
        (results_dir / "j__b.result").write_text("B")

    t = threading.Thread(target=_writer)
    t.start()
    try:
        found = watcher.wait_for_many("j", ["a", "b"], timeout_s=1.0)
        assert set(found) == {"a", "b"}
    finally:
        t.join()


def test_wait_for_many_raises_on_missing(results_dir):
    (results_dir / "j__a.result").write_text("A")
    watcher = ResultWatcher(results_dir, poll_interval_s=0.01)
    with pytest.raises(ResultWatcherTimeoutError, match="b"):
        watcher.wait_for_many("j", ["a", "b"], timeout_s=0.05)


def test_expected_path_format(results_dir):
    watcher = ResultWatcher(results_dir)
    assert watcher.expected_path("abc", "reverse") == results_dir / "abc__reverse.result"
