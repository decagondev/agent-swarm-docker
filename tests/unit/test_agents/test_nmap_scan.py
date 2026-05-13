"""Tests for `NmapScanAgent` — subprocess mocked, no real network."""

import subprocess

import pytest

import agents  # noqa: F401 — triggers @register_agent
from agents.pentest.nmap_scan import NmapScanAgent
from core.registry import REGISTRY

# A realistic-shaped nmap output snippet. Two open TCP ports so the
# regex-based summary count is verifiable.
_FAKE_NMAP_STDOUT = """\
Starting Nmap 7.94 ( https://nmap.org ) at 2026-05-13 13:30 UTC
Nmap scan report for scanme.nmap.org (45.33.32.156)
Host is up (0.16s latency).
Not shown: 95 closed tcp ports (conn-refused)
PORT      STATE    SERVICE    VERSION
22/tcp    open     ssh        OpenSSH 6.6.1p1 Ubuntu 2ubuntu2.13
80/tcp    open     http       Apache httpd 2.4.7 ((Ubuntu))
9929/tcp  filtered nping-echo
31337/tcp filtered Elite
443/tcp   closed   https

Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 12.34 seconds
"""


@pytest.fixture
def _no_dns(monkeypatch):
    """Force the DNS-fallback path so tests are hermetic."""
    import agents.pentest.nmap_scan as mod

    monkeypatch.setattr(mod.socket, "gethostbyname", lambda _: "45.33.32.156")
    return mod


def _mock_run(stdout: str = "", stderr: str = "", returncode: int = 0):
    def _run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )

    return _run


def test_writes_nmap_stdout_to_result_file(monkeypatch, shared_data_dir, _no_dns):
    monkeypatch.setattr(subprocess, "run", _mock_run(stdout=_FAKE_NMAP_STDOUT))
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("scan it", encoding="utf-8")

    result = NmapScanAgent().run(input_path, shared_data_dir / "results", "j")

    assert result.output_path.read_text(encoding="utf-8") == _FAKE_NMAP_STDOUT
    assert result.agent_name == "nmap_scan"
    # The regex counts lines matching "<num>/tcp open" — 2 in the fixture.
    assert "2 open" in result.summary


def test_command_passes_expected_flags(monkeypatch, shared_data_dir, _no_dns):
    captured: dict = {}

    def _capture(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("x", encoding="utf-8")

    NmapScanAgent().run(input_path, shared_data_dir / "results", "j")

    # nmap binary, service-version flag, fast scan flag, target.
    assert captured["args"][0] == "nmap"
    assert "-sV" in captured["args"]
    assert "-F" in captured["args"]
    assert captured["args"][-1] in ("scanme.nmap.org", "45.33.32.156")
    assert captured["kwargs"]["timeout"] == 60


def test_timeout_writes_friendly_error(monkeypatch, shared_data_dir, _no_dns):
    def _raise(*_, **__):
        raise subprocess.TimeoutExpired(cmd=["nmap"], timeout=60)

    monkeypatch.setattr(subprocess, "run", _raise)
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("x", encoding="utf-8")

    result = NmapScanAgent().run(input_path, shared_data_dir / "results", "j")

    assert "# nmap failed: timeout" in result.output_path.read_text(encoding="utf-8")
    assert "TIMEOUT" in result.summary


def test_missing_nmap_binary_handled(monkeypatch, shared_data_dir, _no_dns):
    def _raise(*_, **__):
        raise FileNotFoundError(2, "No such file or directory: 'nmap'")

    monkeypatch.setattr(subprocess, "run", _raise)
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("x", encoding="utf-8")

    result = NmapScanAgent().run(input_path, shared_data_dir / "results", "j")

    assert "binary not installed" in result.output_path.read_text(encoding="utf-8")
    assert "BINARY MISSING" in result.summary


def test_nonzero_exit_surfaces_stderr(monkeypatch, shared_data_dir, _no_dns):
    monkeypatch.setattr(
        subprocess,
        "run",
        _mock_run(stderr="network unreachable", returncode=1),
    )
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("x", encoding="utf-8")

    result = NmapScanAgent().run(input_path, shared_data_dir / "results", "j")

    body = result.output_path.read_text(encoding="utf-8")
    assert "# nmap failed: exit 1" in body
    assert "network unreachable" in body
    assert "exit 1" in result.summary


def test_uses_real_hostname_when_dns_resolves(monkeypatch, shared_data_dir):
    """If DNS works, the agent uses the hostname, not the fallback IP."""
    import agents.pentest.nmap_scan as mod

    monkeypatch.setattr(mod.socket, "gethostbyname", lambda host: "45.33.32.156")
    captured: dict = {}

    def _capture(args, **_):
        captured["target"] = args[-1]
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("x", encoding="utf-8")
    NmapScanAgent().run(input_path, shared_data_dir / "results", "j")

    assert captured["target"] == "scanme.nmap.org"


def test_falls_back_to_ip_on_dns_failure(monkeypatch, shared_data_dir):
    import agents.pentest.nmap_scan as mod

    def _boom(_host):
        raise OSError("DNS down")

    monkeypatch.setattr(mod.socket, "gethostbyname", _boom)
    captured: dict = {}

    def _capture(args, **_):
        captured["target"] = args[-1]
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _capture)
    input_path = shared_data_dir / "input" / "p.txt"
    input_path.write_text("x", encoding="utf-8")
    NmapScanAgent().run(input_path, shared_data_dir / "results", "j")

    assert captured["target"] == "45.33.32.156"


def test_registered_with_singleton():
    assert "nmap_scan" in REGISTRY
    assert REGISTRY.get("nmap_scan") is NmapScanAgent


def test_pentest_tag():
    assert NmapScanAgent.tags == frozenset({"pentest"})
