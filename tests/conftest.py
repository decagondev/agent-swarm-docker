"""Shared pytest fixtures.

Concrete fixtures (FakeLLMClient, FakeDockerClient, SharedVolume tmp_path helper)
land in subsequent commits as the abstractions they fake are introduced.
"""

import os

import pytest


@pytest.fixture
def shared_data_dir(tmp_path):
    """Throwaway shared-volume root mirroring /app/data layout in containers."""
    for sub in ("input", "results", "output"):
        (tmp_path / sub).mkdir()
    return tmp_path


def pytest_collection_modifyitems(config, items):
    """Skip @pytest.mark.integration tests unless DOCKER_SWARM_TESTS=1."""
    if os.environ.get("DOCKER_SWARM_TESTS") == "1":
        return
    skip_marker = pytest.mark.skip(reason="integration tests require DOCKER_SWARM_TESTS=1")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)
