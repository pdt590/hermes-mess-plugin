"""Single-process durable inbox. All methods run on the adapter event loop."""
import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


class Conflict(Exception):
    pass


class Full(Exception):
    pass


@dataclass(frozen=True)
class Receipt:
    id: str
    duplicate: bool


class Inbox:
    def __init__(self, path, capacity=1000, retention_seconds=604800):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=5)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS inbox (
            id TEXT PRIMARY KEY, upstream_key TEXT UNIQUE, digest TEXT NOT NULL,
            payload TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL,
            updated REAL NOT NULL, error TEXT)""")
        self.db.commit()
        self.capacity = capacity
        self.retention = retention_seconds

    def enqueue(self, payload):
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        key = json.dumps([payload["contact_id"], payload["message_id"]]) if payload.get("message_id") else None
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if key:
                previous = self.db.execute("SELECT id,digest FROM inbox WHERE upstream_key=?", (key,)).fetchone()
                if previous:
                    if previous[1] != digest:
                        raise Conflict()
                    return Receipt(previous[0], True)
            count = self.db.execute("SELECT count(*) FROM inbox WHERE state IN ('pending','processing')").fetchone()[0]
            if count >= self.capacity:
                raise Full()
            identifier = uuid.uuid4().hex
            now = time.time()
            self.db.execute("INSERT INTO inbox VALUES (?,?,?,?,?,?,?,NULL)",
                            (identifier, key, digest, encoded, "pending", now, now))
        return Receipt(identifier, False)

    def claim(self):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT id,payload FROM inbox WHERE state='pending' ORDER BY rowid LIMIT 1").fetchone()
            if row:
                self.db.execute("UPDATE inbox SET state='processing',updated=? WHERE id=?", (time.time(), row[0]))
        return (row[0], json.loads(row[1])) if row else None

    def recover(self):
        with self.db:
            self.db.execute("UPDATE inbox SET state='pending' WHERE state='processing'")

    def complete(self, identifier):
        self._finish(identifier, "complete", None)

    def fail(self, identifier, reason):
        self._finish(identifier, "failed", reason)

    def _finish(self, identifier, state, reason):
        with self.db:
            self.db.execute("UPDATE inbox SET state=?,error=?,payload='{}',updated=? WHERE id=?", (state, reason, time.time(), identifier))

    def prune(self, now=None):
        with self.db:
            self.db.execute("DELETE FROM inbox WHERE state IN ('complete','failed') AND updated<?", ((time.time() if now is None else now) - self.retention,))

    def close(self):
        self.db.close()
