"""Utilization reporting over booking history.

Aggregates store.all_bookings() by room, machine, and course, using
schedule.class_meta_by_id() for the stable course/room lookup per class_id
(a class_id's course and room never change even though today_classes()
re-anchors its start/end times to "now" on every call).

All-time totals only — no date-range filtering. Good enough for a demo;
revisit if this is ever used to report on a real multi-week deployment.
"""
import time
from collections import defaultdict


def _duration_seconds(booking: dict, now: float) -> float:
    """Seconds the machine has been held: full session for released/expired
    bookings, elapsed-so-far for still-active ones."""
    if booking["status"] == "active":
        return max(0.0, now - booking["created_at"])
    end = booking["released_at"] or booking["created_at"]
    return max(0.0, end - booking["created_at"])


def _finalize(groups: dict, label_key: str) -> list[dict]:
    rows = []
    for key, g in groups.items():
        durations = g["durations"]
        avg_min = (sum(durations) / len(durations) / 60) if durations else 0.0
        rows.append({
            "key": key,
            "label": g.get(label_key, key),
            "bookings": len(durations),
            "avg_duration_min": round(avg_min, 1),
            "total_duration_min": round(sum(durations) / 60, 1),
        })
    rows.sort(key=lambda r: -r["bookings"])
    return rows


def compute_usage_stats(bookings: list[dict], class_meta: dict[str, dict]) -> dict:
    """bookings: store.all_bookings()-shaped rows.
    class_meta: schedule.class_meta_by_id()-shaped lookup."""
    now = time.time()

    by_room = defaultdict(lambda: {"durations": []})
    by_machine = defaultdict(lambda: {"durations": [], "machine_name": ""})
    by_course = defaultdict(lambda: {"durations": [], "title": ""})

    status_counts = {"active": 0, "released": 0, "expired": 0}
    all_durations = []

    for b in bookings:
        status_counts[b["status"]] = status_counts.get(b["status"], 0) + 1
        duration = _duration_seconds(b, now)
        all_durations.append(duration)

        meta = class_meta.get(b["class_id"], {})
        room = meta.get("room", "Unknown room")
        course_code = meta.get("course_code", "Unknown course")

        by_room[room]["durations"].append(duration)

        mkey = b["machine_id"]
        by_machine[mkey]["durations"].append(duration)
        by_machine[mkey]["machine_name"] = b["machine_name"]

        by_course[course_code]["durations"].append(duration)
        by_course[course_code]["title"] = meta.get("title", "")

    avg_overall_min = round(sum(all_durations) / len(all_durations) / 60, 1) if all_durations else 0.0

    rooms = _finalize(by_room, "room")
    for r in rooms:
        r["label"] = r["key"]

    machines = _finalize(by_machine, "machine_name")
    for m in machines:
        m["label"] = by_machine[m["key"]]["machine_name"] or m["key"]

    courses = _finalize(by_course, "title")
    for c in courses:
        c["label"] = f'{c["key"]} — {by_course[c["key"]]["title"]}' if by_course[c["key"]]["title"] else c["key"]

    return {
        "total_bookings": len(bookings),
        "active_count": status_counts.get("active", 0),
        "released_count": status_counts.get("released", 0),
        "expired_count": status_counts.get("expired", 0),
        "avg_duration_min": avg_overall_min,
        "by_room": rooms,
        "by_machine": machines,
        "by_course": courses,
    }
