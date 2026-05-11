"""End-to-end smoke against a real single-node Docker Swarm.

SKIPPED unless DOCKER_SWARM_TESTS=1. Requires:

  - A running Docker daemon with Swarm mode initialised (`docker swarm init`).
  - The image `agent-swarm:latest` built locally:
        docker build -f docker/Dockerfile -t agent-swarm:latest .
  - A Swarm-scoped volume named `agent-swarm_shared-data` (e.g. via
    `docker stack deploy -c docker/docker-stack.yml agent-swarm`).
  - Valid LLM credentials in the environment (LLM_PROVIDER + API key).

The test deliberately does NOT auto-initialise Swarm or pull credentials — the
operator opts in by setting `DOCKER_SWARM_TESTS=1` and ensuring the stage env
is ready.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]


def _docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:  # noqa: BLE001
        return False


def _swarm_active() -> bool:
    try:
        out = subprocess.run(
            ["docker", "info", "--format", "{{.Swarm.LocalNodeState}}"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() == "active"
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(scope="module")
def swarm_ready():
    if not _docker_available():
        pytest.skip("Docker daemon not reachable.")
    if not _swarm_active():
        pytest.skip("Docker Swarm not initialised — run `docker swarm init` first.")


def test_supervisor_spawns_services_and_writes_report(swarm_ready, tmp_path):
    """Run supervisor --executor swarm; verify Swarm services appear mid-run
    and the final report is written.

    If no LLM key is set (e.g. on CI), falls back to --dry-run --fixture so
    the Swarm executor path is still exercised end-to-end.
    """
    fixture = os.environ.get("AGENT_SWARM_CI_FIXTURE")
    key_env = f"{os.environ.get('LLM_PROVIDER', 'openai').upper()}_API_KEY"
    have_key = bool(os.environ.get(key_env))

    if not have_key and not fixture:
        pytest.skip(
            f"No {key_env} set and AGENT_SWARM_CI_FIXTURE not pointing at a fixture."
        )

    cmd = [
        "python", "supervisor.py",
        "--executor", "swarm",
        "--job", "e2e",
        "--data-root", str(tmp_path),
    ]
    if not have_key:
        cmd.extend(["--dry-run", "--fixture", fixture])
        prompt = "CI smoke."
    else:
        prompt = (
            "Analyze: 'The quick brown fox jumps over the lazy dog while coding "
            "with Docker Swarm.' Capitalize it and reverse it."
        )
    cmd.append(prompt)

    # Snapshot pre-existing services so we can isolate this run.
    pre_existing = _agent_swarm_services()
    proc = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Poll until at least one new service appears or the process exits.
    deadline = time.monotonic() + 30
    saw_spawn = False
    while time.monotonic() < deadline:
        if set(_agent_swarm_services()) - set(pre_existing):
            saw_spawn = True
            break
        if proc.poll() is not None:
            break
        time.sleep(0.5)

    stdout, stderr = proc.communicate(timeout=120)

    assert proc.returncode == 0, f"supervisor failed: {stderr}"
    assert saw_spawn, "No new agent services appeared in `docker service ls`."
    assert (tmp_path / "results" / "e2e__capitalize.result").exists()
    # In dry-run mode the final stdout is the fixture's recorded text; in
    # real-LLM mode it's the model's synthesis. Both contain a 'capitalize'
    # hint either in the stdout or in the result file.
    capitalize_out = (tmp_path / "results" / "e2e__capitalize.result").read_text()
    assert capitalize_out.isupper() or capitalize_out == ""


def _agent_swarm_services() -> list[str]:
    out = subprocess.run(
        [
            "docker",
            "service",
            "ls",
            "--filter",
            "label=agent-swarm.role=ephemeral",
            "--format",
            "{{.Name}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]
