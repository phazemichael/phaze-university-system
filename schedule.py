"""Synthetic university class schedule for the demo.

Design choices (per Michael's call):
- General higher-ed pitch demo, not a named prospect.
- Schedule is hard-coded sample data, not imported from a real SIS.
- Class times are anchored to "now" every time the module loads, so the
  demo always has a class "in session" regardless of when it's actually
  run in front of a prospect.
- Rooms are logical buckets; the machines inside each room are pulled
  live from whatever Phaze org is configured (round-robin split of
  GET /orgs/{id}/machines) rather than hardcoded machine IDs — point this
  demo at a differently-stocked org and it reshuffles automatically.
- Roster emails are synthetic (@sample.edu) EXCEPT one real seat per class
  that's backed by an actual member in the connected Phaze org, so a live
  demo can always prove a real assign/connect — not just browse a fake
  schedule. See `_real_demo_member()`.
- Classes are strictly sequential: only ONE class is in session anywhere
  in the schedule at any given moment, regardless of room (a classroom
  can only host one class at a time in reality). See `today_classes()`'s
  non-overlapping (offset, duration) windows.
"""
from datetime import datetime, timedelta

import phaze_client as phz

ROOM_NAMES = ["Design Lab A", "Design Lab B", "Render Farm Suite"]

SAMPLE_ROSTER = [
    {"name": "Avery Chen", "email": "avery.chen@sample.edu"},
    {"name": "Jordan Lee", "email": "jordan.lee@sample.edu"},
    {"name": "Priya Nair", "email": "priya.nair@sample.edu"},
    {"name": "Sam Rivera", "email": "sam.rivera@sample.edu"},
]

_real_member_cache: dict | None = None
_real_member_checked = False


def _real_demo_member() -> dict | None:
    """First real member in the connected Phaze org, so at least one
    roster seat per class can actually assign/connect live. Cached for
    the process lifetime — restart the app if the org's members change."""
    global _real_member_cache, _real_member_checked
    if not _real_member_checked:
        _real_member_checked = True
        try:
            members = phz.list_members()
            _real_member_cache = members[0] if members else None
        except Exception:
            _real_member_cache = None
    return _real_member_cache


def _roster_for(class_index: int) -> list[dict]:
    roster = list(SAMPLE_ROSTER)
    real = _real_demo_member()
    if real and real.get("email"):
        roster = roster + [{
            "name": f"{real.get('name', 'Demo account')} (live seat)",
            "email": real["email"],
        }]
    return roster


def _rooms_with_machines() -> dict[str, list[dict]]:
    """Split the connected org's live machines round-robin across the
    synthetic room names. Works with any fleet size, including the tiny
    4-machine test org — rooms with no machines just show as empty."""
    try:
        machines = phz.list_machines()
    except Exception:
        machines = []
    rooms: dict[str, list[dict]] = {name: [] for name in ROOM_NAMES}
    for i, m in enumerate(machines):
        rooms[ROOM_NAMES[i % len(ROOM_NAMES)]].append(m)
    return rooms


def today_classes() -> list[dict]:
    """Returns today's synthetic class sessions, anchored relative to
    now() so there is always something 'in session' and something
    'upcoming' no matter when this is called.

    Strictly sequential by design (per Michael): at any given moment only
    ONE class anywhere in the schedule is in session, regardless of room.
    The (start_offset, duration) pairs below are deliberately
    non-overlapping — do not add a class whose window overlaps another's."""
    now = datetime.now()

    def session(course_code, title, room, start_offset_min, duration_min, class_id):
        start = now + timedelta(minutes=start_offset_min)
        end = start + timedelta(minutes=duration_min)
        return {
            "id": class_id,
            "course_code": course_code,
            "title": title,
            "room": room,
            "start": start,
            "end": end,
            "roster": _roster_for(hash(class_id) % 7),
        }

    rooms = ROOM_NAMES
    # Chronological, non-overlapping windows (offset_min, duration_min):
    # (-150, 60) -> (-90, past) | (-20, 40) -> (+20, in session now)
    # | (+20, 60) -> (+80, upcoming) | (+80, 60) -> (+140, upcoming)
    return [
        session("DSGN 310", "Intro to Virtual Production", rooms[0], -150, 60, "dsgn310-earlier"),
        session("DSGN 310", "Intro to Virtual Production", rooms[0], -20, 40, "dsgn310-am"),
        session("FILM 240", "Color Grading Workshop", rooms[1], 20, 60, "film240-am"),
        session("ANIM 455", "Capstone Render Lab", rooms[2], 80, 60, "anim455-pm"),
    ]


def get_class(class_id: str) -> dict | None:
    for c in today_classes():
        if c["id"] == class_id:
            return c
    return None


def classes_for_email(email: str) -> list[dict]:
    email_l = email.strip().lower()
    return [
        c for c in today_classes()
        if any(r["email"].lower() == email_l for r in c["roster"])
    ]


def is_enrolled(class_id: str, email: str) -> bool:
    c = get_class(class_id)
    if not c:
        return False
    email_l = email.strip().lower()
    return any(r["email"].lower() == email_l for r in c["roster"])


def session_status(c: dict) -> str:
    now = datetime.now()
    if now < c["start"]:
        return "upcoming"
    if now > c["end"]:
        return "past"
    return "in_session"


def room_machines(room_name: str) -> list[dict]:
    return _rooms_with_machines().get(room_name, [])
