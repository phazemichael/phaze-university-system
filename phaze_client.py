"""Thin wrapper around the Phaze Enterprise API for the university demo.

Same shape as the generic reservation-demo's phaze_client.py, plus a
room-aware available_machines() variant used to carve the live fleet into
classroom buckets.
"""
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("PHAZE_API_BASE", "https://public-api.phaze.app/enterprise/v1")
API_KEY = os.getenv("PHAZE_API_KEY", "")
ORG_ID = os.getenv("PHAZE_ORG_ID", "")


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=API_BASE,
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=15.0,
    )


def list_machines(org_id: str = ORG_ID) -> list[dict]:
    with _client() as c:
        r = c.get(f"/orgs/{org_id}/machines", params={"limit": 200})
        r.raise_for_status()
        return r.json()["data"]


def available_machine_ids(org_id: str = ORG_ID) -> set[str]:
    """IDs of machines that are online AND unassigned right now."""
    return {
        m["id"] for m in list_machines(org_id)
        if m.get("is_online") and not m.get("assignee_id") and not m.get("group_id")
    }


def list_members(org_id: str = ORG_ID) -> list[dict]:
    with _client() as c:
        r = c.get(f"/orgs/{org_id}/members", params={"limit": 200})
        r.raise_for_status()
        return r.json()["data"]


def find_member_by_email(email: str, org_id: str = ORG_ID) -> dict | None:
    """GET /members?q= is a fuzzy substring match — filter to an exact,
    case-insensitive email match ourselves."""
    email_l = email.strip().lower()
    with _client() as c:
        r = c.get(f"/orgs/{org_id}/members", params={"q": email_l, "limit": 200})
        r.raise_for_status()
        for m in r.json()["data"]:
            if m.get("email", "").strip().lower() == email_l:
                return m
    return None


def assign_machine_to_user(machine_id: str, user_id: str, org_id: str = ORG_ID) -> None:
    with _client() as c:
        r = c.put(
            f"/orgs/{org_id}/machines/assign-user",
            json={"machine_ids": [machine_id], "user_id": user_id},
        )
        r.raise_for_status()


def unassign_machines(machine_ids: list[str], org_id: str = ORG_ID) -> None:
    if not machine_ids:
        return
    with _client() as c:
        r = c.put(
            f"/orgs/{org_id}/machines/unassign",
            json={"machine_ids": machine_ids},
        )
        r.raise_for_status()
