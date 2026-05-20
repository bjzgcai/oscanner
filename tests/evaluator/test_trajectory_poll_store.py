import time

from evaluator.services.trajectory_poll_store import SQLiteTrajectoryPollStore


def test_sqlite_poll_store_persists_events_across_instances(tmp_path):
    db_path = tmp_path / "poll_jobs.sqlite3"

    store = SQLiteTrajectoryPollStore(db_path=db_path, ttl_seconds=3600)
    store.create_job("job-1", created_at=100.0)
    first_id = store.append_event("job-1", "section", {"title": "connected"})
    second_id = store.append_event("job-1", "result", {"success": True})
    store.finish_job("job-1")

    reloaded = SQLiteTrajectoryPollStore(db_path=db_path, ttl_seconds=3600)
    status = reloaded.get_job("job-1", cursor=1)

    assert first_id == 0
    assert second_id == 1
    assert status == {
        "job_id": "job-1",
        "events": [
            {"id": 1, "event": "result", "data": {"success": True}},
        ],
        "next_cursor": 2,
        "done": True,
        "error": None,
    }


def test_sqlite_poll_store_removes_expired_done_jobs(tmp_path):
    db_path = tmp_path / "poll_jobs.sqlite3"
    store = SQLiteTrajectoryPollStore(db_path=db_path, ttl_seconds=10)
    store.create_job("old-job", created_at=100.0)
    store.append_event("old-job", "done", {})
    store.finish_job("old-job")
    store.create_job("running-job", created_at=100.0)

    store.cleanup(now=111.0)

    assert store.get_job("old-job", cursor=0) is None
    assert store.get_job("running-job", cursor=0)["done"] is False


def test_sqlite_poll_store_marks_previous_running_jobs_interrupted(tmp_path):
    db_path = tmp_path / "poll_jobs.sqlite3"
    interrupted_message = "Analysis job interrupted by server restart. Please start a new analysis."
    store = SQLiteTrajectoryPollStore(db_path=db_path, ttl_seconds=3600)
    store.create_job("job-1", created_at=100.0)

    store.mark_interrupted_jobs(
        before_created_at=time.time() + 1,
        message=interrupted_message,
    )

    status = store.get_job("job-1", cursor=0)

    assert status["done"] is True
    assert status["error"] == interrupted_message
