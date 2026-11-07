import pytest

from autoapply.engine.protocol import Engine


@pytest.mark.asyncio
async def test_ping_and_recover(tmp_path, monkeypatch) -> None:
    db = tmp_path / "autoapply.db"
    monkeypatch.setattr("autoapply.engine.protocol.DEFAULT_DB_PATH", db)
    from autoapply.storage import ProfileStore, Tracker

    engine = Engine()
    engine.profiles = ProfileStore(db)
    engine.tracker = Tracker(db, engine=engine.profiles.engine)
    assert (await engine.handle({"cmd": "ping"}))["ok"] is True
    run = engine.tracker.start_run("http://127.0.0.1/")
    engine.tracker.set_run_state(run, "submitting")
    recovered = await engine.handle({"cmd": "recover"})
    assert run in recovered["uncertain_runs"]
