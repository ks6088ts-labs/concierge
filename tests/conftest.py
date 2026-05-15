"""Shared pytest fixtures and helpers for the test suite."""

from __future__ import annotations

import pytest


def skip_if_docker_unavailable() -> None:
    """Skip the current test if a usable Docker daemon is not reachable.

    Integration tests that rely on ``testcontainers`` require a running
    Docker daemon. In environments without Docker (for example, local
    development on a machine where Docker is not installed or not running),
    we skip these tests instead of erroring out at fixture setup.
    """
    try:
        import docker  # noqa: PLC0415

        docker.from_env().ping()
    except Exception as exc:  # docker.errors.DockerException and friends
        pytest.skip(f"Docker is not available: {exc}")
