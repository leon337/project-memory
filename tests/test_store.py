from datetime import datetime, timedelta, timezone
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
    assert claimed["lease_token"]
    assert claimed["attempts"] == 1

    completed = store.complete_task(
        created["id"],
        lease_token=claimed["lease_token"],
        ok=True,
        result={"verified": True},
    )
    assert completed is not None
    assert completed["status"] == "succeeded"
    assert completed["result"] == {"verified": True}


def test_wrong_lease_cannot_complete_task(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    created = store.create_task("abrir example.com")
    claimed = store.claim_next("agent-a")
    assert claimed is not None

    completed = store.complete_task(
        created["id"],
        lease_token="lease-invalido",
        ok=True,
        result={"verified": True},
    )
    assert completed is None
    assert store.get_task(created["id"])["status"] == "running"


def test_live_lease_can_be_renewed_only_by_its_owner(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    created = store.create_task("abrir example.com")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    claimed = store.claim_next("agent-a", lease_seconds=30, now=start)
    assert claimed is not None

    refused = store.renew_lease(
        created["id"],
        lease_token="lease-invalido",
        lease_seconds=30,
        now=start + timedelta(seconds=10),
    )
    assert refused is None
    assert store.get_task(created["id"])["lease_expires_at"] == claimed["lease_expires_at"]

    renewed = store.renew_lease(
        created["id"],
        lease_token=claimed["lease_token"],
        lease_seconds=30,
        now=start + timedelta(seconds=10),
    )
    assert renewed is not None
    assert renewed["lease_expires_at"] == (
        start + timedelta(seconds=40)
    ).isoformat()


def test_expired_lease_cannot_be_revived_or_complete(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    created = store.create_task("abrir example.com")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    claimed = store.claim_next("agent-a", lease_seconds=30, now=start)
    assert claimed is not None
    expired_at = start + timedelta(seconds=31)

    assert (
        store.renew_lease(
            created["id"],
            lease_token=claimed["lease_token"],
            lease_seconds=30,
            now=expired_at,
        )
        is None
    )
    assert (
        store.complete_task(
            created["id"],
            lease_token=claimed["lease_token"],
            ok=True,
            now=expired_at,
        )
        is None
    )
    assert store.get_task(created["id"])["status"] == "running"


def test_expired_lease_is_requeued_and_reclaimed(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    created = store.create_task("abrir example.com")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    first = store.claim_next("agent-a", lease_seconds=30, now=start)
    assert first is not None
    second = store.claim_next(
        "agent-b",
        lease_seconds=30,
        now=start + timedelta(seconds=31),
    )
    assert second is not None
    assert second["id"] == created["id"]
    assert second["agent_id"] == "agent-b"
    assert second["lease_token"] != first["lease_token"]
    assert second["attempts"] == 2


def test_repeated_expiration_eventually_fails_task(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    created = store.create_task("abrir example.com")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    for attempt in range(3):
        claimed = store.claim_next(
            f"agent-{attempt}",
            lease_seconds=30,
            max_attempts=3,
            now=start + timedelta(seconds=31 * attempt),
        )
        assert claimed is not None

    store.recover_expired(
        now=start + timedelta(seconds=31 * 3),
        max_attempts=3,
    )
    task = store.get_task(created["id"])
    assert task is not None
    assert task["status"] == "failed"
    assert "limite de tentativas" in task["error"]


def test_claim_returns_none_when_queue_empty(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    assert store.claim_next("test-agent") is None
