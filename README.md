# Phaze University System

A Flask demo showing how Phaze's remote-display fleet can back a university classroom booking flow: students log in, see today's schedule, and for a class currently in session, grab a free machine in that room and connect to it. The booking auto-releases when the class ends — no manual checkout, no open-ended reservations.

This is a sales-engineering demo, not a production system. The class schedule is synthetic sample data; machine assignment is real, live Phaze API calls against whatever org you point it at.

## How it works

1. **Login** — student enters an email (no password; this is a demo).
2. **My Schedule** — shows the student's classes for "today." Classes are anchored relative to the current time, so there's always one shown as in session and others upcoming, regardless of when you run the demo.
3. **Classroom** — for a class currently in session, shows which machines in that room are free right now, pulled live from the connected Phaze org.
4. **Book** — picks a machine, assigns it to the student's Phaze account, and shows a `phaze://connect?id=...` deep link.
5. **Auto-release** — a background sweeper checks every 15 seconds for bookings whose class has ended and unassigns those machines automatically. Students can also release early from the schedule page.
6. **Admin** — `/admin` shows all classes, their rooms, live machine state, and the booking history.

Design choices worth knowing if you're presenting this:
- Booking is strictly gated to class time — no ad-hoc reservations outside a scheduled session. (See the separate generic `phaze-reservation-demo` for open-ended booking.)
- Only one class is "in session" anywhere in the schedule at any moment, matching how a real room would behave.
- Rooms are logical buckets; the machines inside each one are pulled live from the connected org and split round-robin, so pointing this at a differently-sized org just reshuffles the fleet — no hardcoded machine IDs.
- Each class roster is mostly synthetic `@sample.edu` emails, plus one real seat backed by an actual member in the connected Phaze org, so a live demo can always prove a real assign/connect, not just a browsed fake schedule.

## Requirements

- Python 3.10+
- A Phaze Enterprise API key and org ID with at least a few machines in it

## Setup

```bash
git clone https://github.com/phazemichael/phaze-university-system.git
cd phaze-university-system

python -m venv .venv
source .venv/Scripts/activate   # Windows (git-bash); use .venv/bin/activate on macOS/Linux

pip install -r requirements.txt
```

Create a `.env` file in the project root (never commit this):

```
PHAZE_API_KEY=your_phaze_enterprise_api_key
PHAZE_ORG_ID=your_org_id
PHAZE_API_BASE=https://public-api.phaze.app/enterprise/v1
FLASK_SECRET_KEY=any_random_string
```

## Running it

```bash
python app.py
```

The app starts on `http://127.0.0.1:5056` (see the port in `app.py` if you need to change it) and initializes `bookings.db` (SQLite) on first run.

## Using it for a demo

1. Open `http://127.0.0.1:5056/login` and log in with one of the sample roster emails (check `schedule.py`'s `SAMPLE_ROSTER`) or the live-seat email shown on the schedule page — that one maps to a real member in the connected org and will actually assign a machine.
2. On "My Schedule," pick the class marked **in session** and open it.
3. Pick a free machine and click to book it. This calls the live Phaze API to assign that machine to the student's account.
4. Use the `phaze://connect?id=...` link on the status page to connect, or just narrate it if the Phaze client isn't installed on the demo machine.
5. Visit `/admin` to show the room/machine state and booking history across all classes.
6. To show auto-release, either wait for the class's scheduled end (anchored to when the app started) or click "Release" on the schedule page.

## Project layout

```
app.py              Flask routes: login, schedule, classroom, booking, admin
schedule.py          Synthetic class schedule, rosters, room<->machine mapping
phaze_client.py       Thin wrapper around the Phaze Enterprise API
store.py             SQLite-backed booking storage + auto-expiry queries
templates/            Jinja templates (login, schedule, classroom, status, admin)
static/               CSS theme and fonts
```

## Notes

- `bookings.db`, `.env`, `.venv/`, and `__pycache__/` are gitignored — don't commit real API keys or the local SQLite file.
- The background sweeper thread runs as long as the Flask process is alive; restarting the app clears in-memory caches like the detected "live seat" member (re-detected on first request after restart).
