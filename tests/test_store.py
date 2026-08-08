from pathlib import Path

from context_anchor.store import TaskStore


def test_task_lifecycle(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")

    created = store.create_task("abrir example.com")
    assert created["status"] == "queued"

    claimed = store.claim_next("test-agent")
    assert claimed is not None
    assert claimed["id"] == created["id"]
    assert claimed["status"] == "running"
    assert claimed["agent_id"] == "test-agent"

    completed = store.complete_task(
        created["id"],
        ok=True,
        result={"verified": True},
    )
    assert completed is not None
    assert completed["status"] == "succeeded"
    assert completed["result"] == {"verified": True}


def test_claim_returns_none_when_queue_empty(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    assert store.claim_next("test-agent") is None
