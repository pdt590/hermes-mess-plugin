import pytest


def test_persistence_dedup_conflict_and_no_id(tmp_path):
    from store import Inbox, Conflict
    path = tmp_path / "inbox.sqlite"
    db = Inbox(path, 10, 3600)
    payload = {"contact_id": "123", "message": "hello", "message_id": "a"}
    first = db.enqueue(payload)
    assert not first.duplicate
    assert db.enqueue(payload).duplicate
    with pytest.raises(Conflict):
        db.enqueue({**payload, "message": "different"})
    db.close()
    db = Inbox(path, 10, 3600)
    item = db.claim()
    assert item[0] == first.id
    assert item[1]["message"] == "hello"
    db.recover()
    assert db.claim()[0] == first.id
    db.complete(first.id)
    assert db.enqueue({"contact_id": "123", "message": "hello"}).id != db.enqueue({"contact_id": "123", "message": "hello"}).id
    db.close()


def test_capacity_duplicate_and_prune(tmp_path):
    from store import Inbox, Full
    db = Inbox(tmp_path / "db", 1, 1)
    payload = {"contact_id": "1", "message": "a", "message_id": "a"}
    first = db.enqueue(payload)
    assert db.enqueue(payload).duplicate
    with pytest.raises(Full):
        db.enqueue({"contact_id": "2", "message": "b"})
    db.prune(now=10**12)
    assert db.claim()[0] == first.id
    db.complete(first.id)
    db.prune(now=10**12)
    assert not db.enqueue(payload).duplicate
    db.close()
