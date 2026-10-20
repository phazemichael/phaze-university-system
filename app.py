"""Phaze university classroom scheduler demo — Flask app.

Login (email) -> today's schedule -> for an in-session class you're
enrolled in, see free machines in that room -> book -> auto-released
at the class's scheduled end time (not a chosen duration).

Strictly class-time-gated: a room's machines are only bookable during an
actual scheduled class in that room, for enrolled students — no ad-hoc
booking outside class windows (see the generic phaze-reservation-demo for
that flow instead).
"""
import os
import threading
import time
from datetime import datetime

from flask import Flask, redirect, render_template, request, url_for, flash, session

import phaze_client as phz
import schedule
import store

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")


@app.template_filter("fmt_time")
def fmt_time(dt):
    """12-hour time without a leading zero, portable across OSes
    (%-I is glibc-only and breaks on Windows' Python)."""
    return dt.strftime("%I:%M %p").lstrip("0")


SWEEP_INTERVAL_SEC = 15


def _release(booking: dict, status: str = "expired"):
    phz.unassign_machines([booking["machine_id"]])
    store.release_booking(booking["id"], status=status)


def _sweeper_loop():
    while True:
        try:
            for b in store.expired_active_bookings():
                _release(b, status="expired")
        except Exception as e:
            print(f"[sweeper] error: {e}")
        time.sleep(SWEEP_INTERVAL_SEC)


def start_sweeper():
    t = threading.Thread(target=_sweeper_loop, daemon=True)
    t.start()


def _current_email() -> str | None:
    return session.get("email")


def _require_login():
    if not _current_email():
        return redirect(url_for("login"))
    return None


# ---------------- routes ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email or "@" not in email:
            flash("Enter a valid email address.")
            return redirect(url_for("login"))
        session["email"] = email.lower()
        return redirect(url_for("my_schedule"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def my_schedule():
    redir = _require_login()
    if redir:
        return redir
    email = _current_email()
    classes = schedule.classes_for_email(email)
    for c in classes:
        c["status"] = schedule.session_status(c)
    classes.sort(key=lambda c: c["start"])
    real_member = schedule._real_demo_member()
    return render_template(
        "schedule.html", email=email, classes=classes,
        now=datetime.now(), real_demo_email=(real_member or {}).get("email"),
    )


@app.route("/class/<class_id>")
def class_room(class_id):
    redir = _require_login()
    if redir:
        return redir
    email = _current_email()
    c = schedule.get_class(class_id)
    if not c:
        flash("Class not found.")
        return redirect(url_for("my_schedule"))
    if not schedule.is_enrolled(class_id, email):
        flash("You're not enrolled in that class.")
        return redirect(url_for("my_schedule"))

    status = schedule.session_status(c)
    if status != "in_session":
        flash("This class isn't in session right now — machines are only bookable during class time.")
        return redirect(url_for("my_schedule"))

    existing = store.active_booking_for_class_and_email(class_id, email)
    if existing:
        return redirect(url_for("booking_status", bid=existing["id"]))

    try:
        available_ids = phz.available_machine_ids()
    except Exception:
        available_ids = set()
    room_machines = schedule.room_machines(c["room"])
    free_machines = [m for m in room_machines if m["id"] in available_ids]

    return render_template(
        "classroom.html", c=c, email=email,
        free_machines=free_machines, room_total=len(room_machines),
    )


@app.route("/class/<class_id>/book", methods=["POST"])
def book(class_id):
    redir = _require_login()
    if redir:
        return redir
    email = _current_email()
    c = schedule.get_class(class_id)
    if not c or not schedule.is_enrolled(class_id, email):
        flash("Not enrolled in that class.")
        return redirect(url_for("my_schedule"))
    if schedule.session_status(c) != "in_session":
        flash("Class is no longer in session.")
        return redirect(url_for("my_schedule"))

    existing = store.active_booking_for_class_and_email(class_id, email)
    if existing:
        return redirect(url_for("booking_status", bid=existing["id"]))

    machine_id = request.form.get("machine_id")
    member = phz.find_member_by_email(email)
    if not member:
        flash(
            f"No live Phaze account for {email} in this demo org — "
            f"use the live-seat email shown on your schedule to actually connect."
        )
        return redirect(url_for("class_room", class_id=class_id))

    room_machines = schedule.room_machines(c["room"])
    machine = next((m for m in room_machines if m["id"] == machine_id), None)
    if not machine:
        flash("That machine isn't in this room.")
        return redirect(url_for("class_room", class_id=class_id))

    # Re-check availability right before assigning — a student's "free
    # machine" list can go stale in the seconds between page load and
    # clicking Connect if another student (or this student double-
    # clicking) grabbed it first.
    if machine_id not in phz.available_machine_ids():
        flash(f"{machine['name']} was just taken by someone else — pick another.")
        return redirect(url_for("class_room", class_id=class_id))

    phz.assign_machine_to_user(machine_id, member["id"])
    booking = store.create_booking(
        class_id, email, member["id"], machine_id, machine["name"],
        class_end_at=c["end"].timestamp(),
    )
    return redirect(url_for("booking_status", bid=booking["id"]))


@app.route("/status/<bid>")
def booking_status(bid):
    b = store.get_booking(bid)
    if not b:
        flash("Booking not found.")
        return redirect(url_for("my_schedule"))
    c = schedule.get_class(b["class_id"])
    deep_link = f"phaze://connect?id={b['machine_id']}"
    return render_template("status.html", b=b, c=c, deep_link=deep_link)


@app.route("/status/<bid>/release", methods=["POST"])
def release(bid):
    b = store.get_booking(bid)
    if b and b["status"] == "active":
        _release(b, status="released")
        flash("Machine released.")
    return redirect(url_for("my_schedule"))


@app.route("/admin")
def admin():
    classes = schedule.today_classes()
    for c in classes:
        c["status"] = schedule.session_status(c)
        c["room_machines"] = schedule.room_machines(c["room"])
    classes.sort(key=lambda c: c["start"])
    bookings = store.all_bookings(limit=50)
    active_by_machine = {b["machine_id"]: b for b in store.active_bookings()}
    return render_template(
        "admin.html", classes=classes, bookings=bookings,
        active_by_machine=active_by_machine, rooms=schedule.ROOM_NAMES,
    )


if __name__ == "__main__":
    store.init_db()
    start_sweeper()
    app.run(host="127.0.0.1", port=5056, debug=True, use_reloader=False)
