"""One-off seed script: populate bookings.db with plausible historical data
so the /admin Utilization panel has something to show in a demo, instead of
'No bookings yet.' everywhere. Safe to re-run (clears previous mock rows
only, tagged via the 'mockseed' email domain prefix won't collide with real
@sample.edu or live-org traffic). Not part of the app's normal runtime.
"""
import random
import sqlite3
import time
import uuid
from pathlib import Path

DB_PATH = Path(__file__).with_name("bookings.db")

CLASSES = ["dsgn310-earlier", "dsgn310-am", "film240-am", "anim455-pm"]
ROOMS_BY_CLASS = {
    "dsgn310-earlier": "Design Lab A",
    "dsgn310-am": "Design Lab A",
    "film240-am": "Design Lab B",
    "anim455-pm": "Render Farm Suite",
}
EMAILS = [
    "avery.chen@sample.edu", "jordan.lee@sample.edu",
    "priya.nair@sample.edu", "sam.rivera@sample.edu",
    "taylor.brooks@sample.edu", "morgan.diaz@sample.edu",
    "casey.wong@sample.edu", "riley.patel@sample.edu",
]

# Named machines (normal case) plus a handful of legacy/unnamed ones
# (empty machine_name) so the utilization tables don't look too tidy —
# real fleets always have a few stragglers with missing metadata.
MACHINES = {
    "Design Lab A": [
        ("dlab-a-01", "Design Lab A - 01"),
        ("dlab-a-02", "Design Lab A - 02"),
        ("dlab-a-03", "Design Lab A - 03"),
        ("dlab-a-legacy-07", ""),  # blank name
    ],
    "Design Lab B": [
        ("dlab-b-01", "Design Lab B - 01"),
        ("dlab-b-02", "Design Lab B - 02"),
        ("dlab-b-legacy-04", ""),  # blank name
    ],
    "Render Farm Suite": [
        ("render-01", "Render Farm Suite - 01"),
        ("render-02", "Render Farm Suite - 02"),
        ("render-03", "Render Farm Suite - 03"),
        ("render-unassigned-09", ""),  # blank name
    ],
}


def seed(n_bookings: int = 60, days_back: int = 14) -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS bookings ("
        "id TEXT PRIMARY KEY, class_id TEXT NOT NULL, email TEXT NOT NULL,"
        " user_id TEXT NOT NULL, machine_id TEXT NOT NULL, machine_name TEXT NOT NULL,"
        " created_at REAL NOT NULL, class_end_at REAL NOT NULL, released_at REAL,"
        " status TEXT NOT NULL DEFAULT 'active')"
    )
    # Clear previously seeded rows only (tagged by synthetic user_id prefix).
    conn.execute("DELETE FROM bookings WHERE user_id LIKE 'mockseed-%'")

    now = time.time()
    rows = []
    for _ in range(n_bookings):
        class_id = random.choice(CLASSES)
        room = ROOMS_BY_CLASS[class_id]
        machine_id, machine_name = random.choice(MACHINES[room])
        email = random.choice(EMAILS)
        created_at = now - random.uniform(0, days_back * 86400)
        duration_min = random.choice([12, 18, 25, 30, 35, 40, 45, 55])
        class_end_at = created_at + duration_min * 60
        status = random.choices(["released", "expired"], weights=[0.7, 0.3])[0]
        released_at = class_end_at
        rows.append((
            str(uuid.uuid4()), class_id, email, f"mockseed-{uuid.uuid4().hex[:8]}",
            machine_id, machine_name, created_at, class_end_at, released_at, status,
        ))

    conn.executemany(
        "INSERT INTO bookings (id, class_id, email, user_id, machine_id, machine_name,"
        " created_at, class_end_at, released_at, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    count = seed()
    print(f"Seeded {count} mock bookings into {DB_PATH}")
