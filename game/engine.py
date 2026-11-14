"""Bug Hunt leaderboard: pure logic (no I/O, no network). Easy to unit-test.

The game itself runs instantly in the browser (docs/, GitHub Pages). The page queues
every catch the player hasn't sent yet; "Add to the leaderboard" opens one issue for
all of them (up to MAX_PER_ISSUE), titled

    bughunt: record <bug id>/<r|c> <bug id>/<r|c> ...

(the old single form `bughunt: record <bug id> <report|code>` still works). The bot
validates it and adds every catch to the Bugdex and leaderboard on the profile.
Points are exactly what the game page shows (rarity points, x2 for code), with no
hidden bonus, so the page and the board always agree.
This is an honour system: a browser game can't prove a catch, so the daily limit
keeps spam in check.
"""
from __future__ import annotations

import re
from typing import Any

RECORD_RE = re.compile(r"^\s*bughunt\s*:\s*record\s+([a-z][a-z-]{0,39})\s+(report|code)\s*$", re.IGNORECASE)
BATCH_RE = re.compile(r"^\s*bughunt\s*:\s*record((?:\s+[a-z][a-z-]{0,39}/[rc])+)\s*$", re.IGNORECASE)
LEGACY_RE = re.compile(r"^\s*bughunt\s*:\s*catch\s*$", re.IGNORECASE)
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")

DAILY_LIMIT = 30
MAX_PER_ISSUE = 10
CODE_MULTIPLIER = 2
STATE_VERSION = 5
RECENT_KEEP = 8
PROCESSED_KEEP = 500
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]


def parse_title(title: Any) -> dict | None:
    """{'kind': 'record', 'entries': [(bug, mode), ...]} | {'kind': 'legacy'} | {'kind': 'unknown'}
    | None (unrelated issue)."""
    if not isinstance(title, str) or len(title) > 256:
        return None
    m = RECORD_RE.match(title)
    if m:
        return {"kind": "record", "entries": [(m.group(1).lower(), m.group(2).lower())]}
    m = BATCH_RE.match(title)
    if m:
        entries = []
        for token in m.group(1).split():
            bug, mode = token.lower().split("/")
            entries.append((bug, "code" if mode == "c" else "report"))
        if len(entries) <= MAX_PER_ISSUE:
            return {"kind": "record", "entries": entries}
        return {"kind": "unknown"}
    if LEGACY_RE.match(title):
        return {"kind": "legacy"}
    if title.strip().lower().startswith("bughunt"):
        return {"kind": "unknown"}
    return None


def valid_login(login: Any) -> bool:
    return isinstance(login, str) and bool(LOGIN_RE.match(login)) and not login.endswith("-")


def initial_state(bugs: list[dict]) -> dict:
    return {"version": STATE_VERSION, "total": 0, "counts": {b["id"]: 0 for b in bugs},
            "hunters": {}, "recent": [], "processed": []}


def mark_processed(state: dict, issue: int) -> None:
    if issue not in state["processed"]:
        state["processed"].append(issue)
        del state["processed"][:-PROCESSED_KEEP]


def rarity_rank(rarity: str) -> int:
    return RARITY_ORDER.index(rarity)


def catch_points(data: dict, bug_id: str, mode: str) -> int:
    """Rarity points, doubled for code. The game page uses the same rule."""
    bug = next(b for b in data["bugs"] if b["id"] == bug_id)
    return data["rarities"][bug["rarity"]]["points"] * (CODE_MULTIPLIER if mode == "code" else 1)


def _add_catch(state: dict, data: dict, login: str, when_iso: str, issue: int, bug_id: str, mode: str) -> dict:
    """Add one catch (its issue is already marked processed). status: recorded, unknown_bug, limit."""
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

    points = catch_points(data, bug_id, mode)
    first_ever = state["counts"].get(bug_id, 0) == 0
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
    return {"status": "recorded", "bug": bug, "mode": mode, "points": points, "first_ever": first_ever}


def record_batch(state: dict, data: dict, login: str, when_iso: str, issue: int,
                 entries: list) -> dict:
    """Add every catch from one leaderboard issue.

    Returns {status, results, recorded, points, hunter}; status is recorded (at least one
    catch counted), duplicate (issue seen before), or the first entry's failure."""
    if not valid_login(login):
        raise ValueError("invalid login")
    if issue in state["processed"]:
        return {"status": "duplicate", "results": [], "recorded": [], "points": 0, "hunter": None}
    mark_processed(state, issue)
    results = [_add_catch(state, data, login, when_iso, issue, bug, mode) for bug, mode in entries]
    recorded = [r for r in results if r["status"] == "recorded"]
    hunter = state["hunters"].get(login)
    status = "recorded" if recorded else (results[0]["status"] if results else "unknown_bug")
    return {"status": status, "results": results, "recorded": recorded,
            "points": sum(r["points"] for r in recorded), "hunter": dict(hunter) if hunter else None}


def record_catch(state: dict, data: dict, login: str, when_iso: str, issue: int,
                 bug_id: str, mode: str) -> dict:
    """One catch from one issue (used by tests and the preview). status: recorded, unknown_bug, limit, duplicate."""
    batch = record_batch(state, data, login, when_iso, issue, [(bug_id, mode)])
    if batch["status"] == "duplicate":
        return batch
    return dict(batch["results"][0], hunter=batch["hunter"])


def migrate(state: dict, data: dict) -> dict:
    """v4 -> v5. v4 added a hidden +3 for the first catch of each bug on the board, which the
    game page never showed, so the two scores disagreed. Recompute every hunter's points from
    the full history when the state still holds all of it."""
    if state.get("version") == 4:
        known = {b["id"] for b in data["bugs"]}
        if state["total"] == len(state["recent"]):
            for hunter in state["hunters"].values():
                hunter["points"] = 0
            for r in state["recent"]:
                if r["login"] in state["hunters"] and r["bug"] in known:
                    state["hunters"][r["login"]]["points"] += catch_points(data, r["bug"], r.get("mode", "report"))
        state["version"] = STATE_VERSION
    return state


def leaderboard(state: dict, n: int = 5) -> list[tuple[str, dict]]:
    rows = [r for r in state["hunters"].items() if r[1]["catches"] > 0]
    rows.sort(key=lambda kv: (-kv[1]["points"], -kv[1]["catches"], kv[0].lower()))
    return rows[:n]


def discovered(state: dict) -> int:
    return sum(1 for c in state["counts"].values() if c > 0)
