# Task 14 (fly deploy prep): Fly mounts an EMPTY volume on first boot -- the
# vector pickle is seeded onto it manually AFTER the machine is already up
# (task-14-brief.md Step 4), so `lifespan` seeing a missing/unreadable store
# on the very first boot is the expected case, not a bug. Before this fix
# `VectorStore.load` was called with no error handling, so that first boot
# would crash-loop and there'd be no running machine left to `fly ssh
# console` into to seed it -- chicken and egg. This test drives `lifespan`
# directly (no TestClient/network/API key needed, same convention
# test_friendly_errors.py uses for another asyncio coroutine) and asserts
# the app stays up and /health reports not-ready instead of crashing.
import asyncio

import pytest
from fastapi import HTTPException

from rulesagent.api import main


def test_lifespan_survives_missing_vector_store(monkeypatch):
    def _boom(cls, path):
        raise FileNotFoundError(f"no vector store at {path} -- volume not seeded yet")

    monkeypatch.setattr(main.VectorStore, "load", classmethod(_boom))
    main._state.clear()

    async def _run():
        async with main.lifespan(main.app):
            # Startup must not raise -- the process stays alive and serving.
            assert "agent" not in main._state
            assert "chunk_map" not in main._state
            assert main.health() == {"status": "ok", "ready": False}

    asyncio.run(_run())
    # lifespan's teardown (`_state.clear()`) still runs cleanly afterward.
    assert main._state == {}


def test_require_agent_raises_friendly_503_when_not_ready():
    main._state.clear()
    with pytest.raises(HTTPException) as exc_info:
        main._require_agent()
    assert exc_info.value.status_code == 503
    assert "starting up" in exc_info.value.detail.lower()
