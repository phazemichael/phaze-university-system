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

# Recurring weekly meeting days per course, Monday=0 .. Sunday=6 — a real
# course schedule pattern (MWF / TTh), used only for the informational
# weekly grid. Today's actual session keeps using the live-anchored
# CLASS_DEFS offsets below so the "always one class in session" demo trick
# still works regardless of which real weekday it is.
COURSE_DAYS = {
    "DSGN 310": [0, 2, 4],  # Mon / Wed / Fri
    "FILM 240": [1, 3],     # Tue / Thu
    "ANIM 455": [0, 2, 4],  # Mon / Wed / Fri
}
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

SAMPLE_ROSTER = [
    {"name": "Avery Chen", "email": "avery.chen@sample.edu"},
    {"name": "Jordan Lee", "email": "jordan.lee@sample.edu"},
    {"name": "Priya Nair", "email": "priya.nair@sample.edu"},
    {"name": "Sam Rivera", "email": "sam.rivera@sample.edu"},
]

_real_member_cache: dict | None = None
_real_member_checked = False


LIVE_SEAT_EMAIL = "michael@phaze.app"


def _real_demo_member() -> dict | None:
    """The designated live-seat member (LIVE_SEAT_EMAIL) in the connected
    Phaze org, so at least one roster seat per class can actually
    assign/connect live. Falls back to the first org member if that email
    isn't present. Cached for the process lifetime — restart the app if
    the org's members change."""
    global _real_member_cache, _real_member_checked
    if not _real_member_checked:
        _real_member_checked = True
        try:
            member = phz.find_member_by_email(LIVE_SEAT_EMAIL)
            if not member:
                members = phz.list_members()
                member = members[0] if members else None
            _real_member_cache = member
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


# Static (class_id, course_code, title, room, start_offset_min, duration_min)
# definitions — the source of truth for both today's live schedule
# (today_classes(), windows re-anchored to "now" on every call) and the
# stable per-class metadata used for historical reporting (class_meta_by_id()),
# where a class_id must keep mapping to the same course/room even though its
# start/end keep sliding relative to "now".
#
# Chronological, non-overlapping windows (offset_min, duration_min):
# (-150, 60) -> (-90, past) | (-20, 40) -> (+20, in session now)
# | (+20, 60) -> (+80, upcoming) | (+80, 60) -> (+140, upcoming)
CLASS_DEFS = [
    ("dsgn310-earlier", "DSGN 310", "Intro to Virtual Production", ROOM_NAMES[0], -150, 60),
    ("dsgn310-am", "DSGN 310", "Intro to Virtual Production", ROOM_NAMES[0], -20, 40),
    ("film240-am", "FILM 240", "Color Grading Workshop", ROOM_NAMES[1], 20, 60),
    ("anim455-pm", "ANIM 455", "Capstone Render Lab", ROOM_NAMES[2], 80, 60),
]


def today_classes() -> list[dict]:
    """Returns today's synthetic class sessions, anchored relative to
    now() so there is always something 'in session' and something
    'upcoming' no matter when this is called.

    Strictly sequential by design (per Michael): at any given moment only
    ONE class anywhere in the schedule is in session, regardless of room."""
    now = datetime.now()
    classes = []
    for class_id, course_code, title, room, start_offset_min, duration_min in CLASS_DEFS:
        start = now + timedelta(minutes=start_offset_min)
        end = start + timedelta(minutes=duration_min)
        classes.append({
            "id": class_id,
            "course_code": course_code,
            "title": title,
            "room": room,
            "start": start,
            "end": end,
            "roster": _roster_for(hash(class_id) % 7),
        })
    return classes


def class_meta_by_id() -> dict[str, dict]:
    """Stable course_code/title/room lookup per class_id, independent of
    today's shifting start/end windows. Used for reporting against
    historical bookings."""
    return {
        class_id: {"course_code": course_code, "title": title, "room": room}
        for class_id, course_code, title, room, *_ in CLASS_DEFS
    }


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


def week_schedule(email: str) -> list[dict]:
    """Mon-Fri recurring view for the student's enrolled courses.

    Informational only — booking still goes through today_classes() /
    get_class(), gated to whatever's actually in session right now. Today's
    column reuses the live-anchored session (so it matches the "see free
    machines" link and the in-session countdown); other days synthesize a
    display time from the course's recurring slot, carrying no class_id to
    book against.
    """
    email_l = email.strip().lower()
    today_list = today_classes()
    # One representative live session per course_code: the non-"earlier"
    # CLASS_DEFS entry is today's actual current/next session for that course.
    representative: dict[str, dict] = {}
    for c in today_list:
        if not c["id"].endswith("-earlier"):
            representative[c["course_code"]] = c

    today_date = datetime.now().date()
    monday = today_date - timedelta(days=today_date.weekday())

    week: list[dict] = []
    for day_offset, day_name in enumerate(WEEKDAY_NAMES):
        day_date = monday + timedelta(days=day_offset)
        is_today = day_date == today_date
        entries = []
        for course_code, days in COURSE_DAYS.items():
            if day_offset not in days:
                continue
            rep = representative.get(course_code)
            if not rep:
                continue
            if not any(r["email"].lower() == email_l for r in rep["roster"]):
                continue  # not enrolled in this course
            if is_today:
                start, end, class_id, status = (
                    rep["start"], rep["end"], rep["id"], session_status(rep),
                )
            else:
                start = datetime.combine(day_date, rep["start"].time())
                end = datetime.combine(day_date, rep["end"].time())
                class_id = None  # informational only, not bookable
                status = "scheduled" if day_date > today_date else "past"
            entries.append({
                "course_code": course_code, "title": rep["title"],
                "room": rep["room"], "start": start, "end": end,
                "class_id": class_id, "status": status,
            })
        entries.sort(key=lambda e: e["start"])
        week.append({"day_name": day_name, "date": day_date, "is_today": is_today, "entries": entries})
    return week
