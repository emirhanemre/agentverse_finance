"""Argon and Flash race for the hedge rationale; the run never waits on a slow Argon. Stand-in models only."""
import asyncio

import pytest

from pubhedge_svc import chain  # first: it puts pubhedge_core on the path
from pubhedge_core.limits import DEFAULT_LIMITS  # noqa: E402


@pytest.fixture
def fake_models(monkeypatch):
    monkeypatch.setattr(chain, "live_models_allowed", lambda: True)
    monkeypatch.setattr(chain, "add_spend", lambda *a: None)

    async def agent(run, step, model, instruction, fns, context):
        return f"{step} done.", 0, 0
    monkeypatch.setattr(chain, "_run_agent", agent)

    def set_models(argon_delay, flash_delay, flash_fails=False):
        async def call(model, facts):
            if model == chain.MODEL_REASONING:
                await asyncio.sleep(argon_delay)
                return "- Argon rationale.", 0, 0
            await asyncio.sleep(flash_delay)
            if flash_fails:
                raise RuntimeError("flash down")
            return "- Flash rationale.", 0, 0
        monkeypatch.setattr(chain, "_rationale_call", call)
    return set_models


def run():
    events = []
    asyncio.run(chain.run_chain("scenario", events.append, dict(DEFAULT_LIMITS)))
    return next(e for e in events if e["type"] == "rationale")


def test_slow_argon_falls_back_to_flagged_flash(fake_models):
    fake_models(argon_delay=5, flash_delay=0)
    r = run()
    assert r["model"] == chain.MODEL_FAST and r["note"] == "Flash used, Argon not back yet"
    assert "Flash rationale" in r["text"]


def test_argon_back_in_time_wins(fake_models):
    fake_models(argon_delay=0, flash_delay=0.5)
    r = run()
    assert r["model"] == chain.MODEL_REASONING and r["note"] is None
    assert "Argon rationale" in r["text"]


def test_flash_failing_waits_for_argon(fake_models):
    fake_models(argon_delay=0.3, flash_delay=0, flash_fails=True)
    r = run()
    assert r["model"] == chain.MODEL_REASONING and "Argon rationale" in r["text"]
