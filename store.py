"""SQLite-backed store for classroom machine bookings.

Separate from Phaze's own state (same pattern as the generic reservation
demo) — Phaze doesn't know about "classes" or "sessions," only
assign/unassign. A booking here auto-expires at the class's scheduled end
time (absolute wall-clock), not an arbitrary duration a student picks.
"""
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).with_name("bookings.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY,
    class_id TEXT NOT NULL,
    email TEXT NOT NULL,
    user_id TEXT NOT NULL,
    machine_id TEXT NOT NULL,
    machine_name TEXT NOT NULL,
    created_at REAL NOT NULL,
    class_end_at REAL NOT NULL,
    released_at REAL,
    status TEXT NOT NULL DEFAULT 'active'  -- active | released | expired
);
"""


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as c:
        c.executescript(SCHEMA)


def create_booking(class_id: str, email: str, user_id: str, machine_id: str,
                    machine_name: str, class_end_at: float) -> dict:
    bid = str(uuid.uuid4())
    now = time.time()
    email_l = email.strip().lower()
    with _conn() as c:
        c.execute(
            "INSERT INTO bookings (id, class_id, email, user_id, machine_id, machine_name,"
            " created_at, class_end_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')",
            (bid, class_id, email_l, user_id, machine_id, machine_name, now, class_end_at),
        )
    return get_booking(bid)


def get_booking(bid: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM bookings WHERE id = ?", (bid,)).fetchone()
        return dict(row) if row else None


def active_booking_for_class_and_email(class_id: str, email: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM bookings WHERE class_id = ? AND email = ? AND status = 'active'",
            (class_id, email.strip().lower()),
        ).fetchone()
        return dict(row) if row else None


def active_booking_for_machine(machine_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM bookings WHERE machine_id = ? AND status = 'active'", (machine_id,)
        ).fetchone()
        return dict(row) if row else None


def active_bookings() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM bookings WHERE status = 'active' ORDER BY class_end_at"
        ).fetchall()
        return [dict(r) for r in rows]


def expired_active_bookings() -> list[dict]:
    now = time.time()
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM bookings WHERE status = 'active' AND class_end_at <= ?", (now,)
        ).fetchall()
        return [dict(r) for r in rows]


def release_booking(bid: str, status: str = "released") -> dict | None:
    b = get_booking(bid)
    if not b or b["status"] != "active":
        return b
    with _conn() as c:
        c.execute(
            "UPDATE bookings SET status = ?, released_at = ? WHERE id = ?",
            (status, time.time(), bid),
        )
    return get_booking(bid)


def all_bookings(limit: int = 100) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM bookings ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
