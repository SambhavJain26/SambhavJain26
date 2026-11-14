"""Bug Hunt leaderboard: pure logic (no I/O, no network). Easy to unit-test.

The game itself runs instantly in the browser (docs/, GitHub Pages). After a catch,
a player can choose "Add me to the leaderboard", which opens an issue titled

    bughunt: record <bug id> <report|code>

The bot validates it and adds the catch to the Bugdex and leaderboard on the profile.
This is an honour system: a browser game can't prove a catch, so the daily limit
keeps spam in check.
"""
from __future__ import annotations

import re
from typing import Any

RECORD_RE = re.compile(r"^\s*bughunt\s*:\s*record\s+([a-z][a-z-]{0,39})\s+(report|code)\s*$", re.IGNORECASE)
LEGACY_RE = re.compile(r"^\s*bughunt\s*:\s*catch\s*$", re.IGNORECASE)
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")

DAILY_LIMIT = 10
CODE_MULTIPLIER = 2
DISCOVERER_BONUS = 3
RECENT_KEEP = 8
PROCESSED_KEEP = 500
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]


def parse_title(title: Any) -> dict | None:
    """{'kind': 'record', bug, mode} | {'kind': 'legacy'} | {'kind': 'unknown'} | None (unrelated issue)."""
    if not isinstance(title, str) or len(title) > 200:
        return None
    m = RECORD_RE.match(title)
    if m:
        return {"kind": "record", "bug": m.group(1).lower(), "mode": m.group(2).lower()}
    if LEGACY_RE.match(title):
        return {"kind": "legacy"}
    if title.strip().lower().startswith("bughunt"):
        return {"kind": "unknown"}
    return None


def valid_login(login: Any) -> bool:
    return isinstance(login, str) and bool(LOGIN_RE.match(login)) and not login.endswith("-")


def initial_state(bugs: list[dict]) -> dict:
    return {"version": 4, "total": 0, "counts": {b["id"]: 0 for b in bugs},
            "hunters": {}, "recent": [], "processed": []}


def mark_processed(state: dict, issue: int) -> None:
    if issue not in state["processed"]:
        state["processed"].append(issue)
        del state["processed"][:-PROCESSED_KEEP]


def rarity_rank(rarity: str) -> int:
    return RARITY_ORDER.index(rarity)


def record_catch(state: dict, data: dict, login: str, when_iso: str, issue: int,
                 bug_id: str, mode: str) -> dict:
    """Add one catch to the board. status: recorded, unknown_bug, limit, duplicate."""
    if not valid_login(login):
        raise ValueError("invalid login")
    if issue in state["processed"]:
        return {"status": "duplicate"}
    mark_processed(state, issue)
    bugs = {b["id"]: b for b in data["bugs"]}
    bug = bugs.get(bug_id)
    if bug is None or mode not in ("report", "code"):
        return {"status": "unknown_bug"}
    day = when_iso[:10]
    hunter = state["hunters"].setdefault(login, {"catches": 0, "points": 0, "best": None, "day": day, "today": 0})
    if hunter["day"] != day:
        hunter["day"], hunter["today"] = day, 0
    if hunter["today"] >= DAILY_LIMIT:
        return {"status": "limit", "limit": DAILY_LIMIT}

    points = data["rarities"][bug["rarity"]]["points"] * (CODE_MULTIPLIER if mode == "code" else 1)
    first_ever = state["counts"].get(bug_id, 0) == 0
    if first_ever:
        points += DISCOVERER_BONUS
    state["counts"][bug_id] = state["counts"].get(bug_id, 0) + 1
    state["total"] += 1
    hunter["today"] += 1
    hunter["catches"] += 1
    hunter["points"] += points
    best = bugs.get(hunter["best"]) if hunter["best"] else None
    if best is None or rarity_rank(bug["rarity"]) > rarity_rank(best["rarity"]):
        hunter["best"] = bug_id
    state["recent"].insert(0, {"login": login, "bug": bug_id, "at": when_iso, "issue": issue, "mode": mode})
    del state["recent"][RECENT_KEEP:]
    return {"status": "recorded", "bug": bug, "mode": mode, "points": points, "first_ever": first_ever,
            "hunter": dict(hunter)}


def leaderboard(state: dict, n: int = 5) -> list[tuple[str, dict]]:
    rows = [r for r in state["hunters"].items() if r[1]["catches"] > 0]
    rows.sort(key=lambda kv: (-kv[1]["points"], -kv[1]["catches"], kv[0].lower()))
    return rows[:n]


def discovered(state: dict) -> int:
    return sum(1 for c in state["counts"].values() if c > 0)
