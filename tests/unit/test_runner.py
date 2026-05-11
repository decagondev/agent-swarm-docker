"""Tests for the `python -m agents.runner` entrypoint."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agents.runner", *args],
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
        check=False,
    )


@pytest.fixture
def data_root(tmp_path):
    """Throwaway shared-volume root with input/ pre-created."""
    (tmp_path / "input").mkdir()
    return tmp_path


def test_capitalize_via_runner(data_root):
    (data_root / "input" / "j1.txt").write_text("hello", encoding="utf-8")
    proc = _run("--agent", "capitalize", "--job", "j1", "--data-root", str(data_root))

    assert proc.returncode == 0, proc.stderr
    result = data_root / "results" / "j1__capitalize.result"
    assert result.read_text(encoding="utf-8") == "HELLO"
    assert "CAPITALIZED" in proc.stdout


def test_reverse_via_runner(data_root):
    (data_root / "input" / "j2.txt").write_text("abc", encoding="utf-8")
    proc = _run("--agent", "reverse", "--job", "j2", "--data-root", str(data_root))

    assert proc.returncode == 0, proc.stderr
    assert (data_root / "results" / "j2__reverse.result").read_text() == "cba"


def test_count_consonants_via_runner(data_root):
    (data_root / "input" / "j3.txt").write_text("hello world", encoding="utf-8")
    proc = _run(
        "--agent", "count_consonants", "--job", "j3", "--data-root", str(data_root)
    )

    assert proc.returncode == 0, proc.stderr
    # 7 consonants: h,l,l,w,r,l,d
    assert (data_root / "results" / "j3__count_consonants.result").read_text() == "7"


def test_vowel_random_via_runner(data_root):
    (data_root / "input" / "j4.txt").write_text("aeiou", encoding="utf-8")
    proc = _run(
        "--agent", "vowel_random", "--job", "j4", "--data-root", str(data_root)
    )

    assert proc.returncode == 0, proc.stderr
    out = (data_root / "results" / "j4__vowel_random.result").read_text()
    assert len(out) == 10  # 5 vowels × 2
    assert out.isalnum()


def test_missing_input_returns_2(data_root):
    proc = _run("--agent", "capitalize", "--job", "nope", "--data-root", str(data_root))

    assert proc.returncode == 2
    assert "input file not found" in proc.stderr


def test_unknown_agent_rejected_by_argparse(data_root):
    (data_root / "input" / "j.txt").write_text("x", encoding="utf-8")
    proc = _run("--agent", "no_such_agent", "--job", "j", "--data-root", str(data_root))

    assert proc.returncode == 2
    assert "invalid choice" in proc.stderr


def test_data_root_env_var(data_root, monkeypatch):
    (data_root / "input" / "envjob.txt").write_text("y", encoding="utf-8")
    monkeypatch.setenv("DATA_ROOT", str(data_root))

    proc = subprocess.run(
        [sys.executable, "-m", "agents.runner", "--agent", "capitalize", "--job", "envjob"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**dict(__import__("os").environ), "DATA_ROOT": str(data_root)},
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert (data_root / "results" / "envjob__capitalize.result").read_text() == "Y"
