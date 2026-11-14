"""Bug Hunt: pure game logic (no I/O, no network). Easy to unit-test.

State shape (game/state.json):
{
  "version": 1,
  "total": 0,
  "counts": {"<bug id>": int},
  "hunters": {"<login>": {"catches": int, "points": int, "best": "<bug id>",
                          "day": "YYYY-MM-DD", "today": int}},
  "recent": [{"login": str, "bug": str, "at": "ISO time", "issue": int}],   # newest first
  "processed": [issue numbers]                                              # newest last
}
"""
from __future__ import annotations

import random
import re
from typing import Any

TITLE_PREFIX = "bughunt"
CATCH_RE = re.compile(r"^\s*bughunt\s*:\s*catch\s*$", re.IGNORECASE)
# GitHub logins: 1-39 chars, alphanumerics or single hyphens, not starting with a hyphen.
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")

DAILY_LIMIT = 10
RECENT_KEEP = 8
PROCESSED_KEEP = 500
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]


def initial_state(bugs: list[dict]) -> dict:
    return {"version": 1, "total": 0, "counts": {b["id"]: 0 for b in bugs},
            "hunters": {}, "recent": [], "processed": []}


def classify_title(title: Any) -> str | None:
    """'catch' for a valid catch, 'unknown' for other bughunt titles, None for unrelated issues."""
    if not isinstance(title, str) or len(title) > 200:
        return None
    if CATCH_RE.match(title):
        return "catch"
    if title.strip().lower().startswith(TITLE_PREFIX):
        return "unknown"
    return None


def valid_login(login: Any) -> bool:
    return isinstance(login, str) and bool(LOGIN_RE.match(login)) and not login.endswith("-")


def pick_bug(bugs: list[dict], rng: random.Random) -> dict:
    weights = [float(b["weight"]) for b in bugs]
    return rng.choices(bugs, weights=weights, k=1)[0]


def rarity_rank(rarity: str) -> int:
    return RARITY_ORDER.index(rarity)


def apply_catch(state: dict, data: dict, login: str, when_iso: str, issue: int,
                rng: random.Random) -> dict:
    """Mutate `state` for one catch attempt and return a result dict.

    result["status"] is one of: "caught", "limit", "duplicate".
    """
    if not valid_login(login):
        raise ValueError("invalid login")
    if issue in state["processed"]:
        return {"status": "duplicate"}

    bugs, rarities = data["bugs"], data["rarities"]
    by_id = {b["id"]: b for b in bugs}
    day = when_iso[:10]
    hunter = state["hunters"].setdefault(
        login, {"catches": 0, "points": 0, "best": None, "day": day, "today": 0})
    if hunter["day"] != day:
        hunter["day"], hunter["today"] = day, 0

    state["processed"].append(issue)
    del state["processed"][:-PROCESSED_KEEP]

    if hunter["today"] >= DAILY_LIMIT:
        return {"status": "limit", "limit": DAILY_LIMIT}

    bug = pick_bug(bugs, rng)
    points = rarities[bug["rarity"]]["points"]
    first_ever = state["counts"].get(bug["id"], 0) == 0

    state["counts"][bug["id"]] = state["counts"].get(bug["id"], 0) + 1
    state["total"] += 1
    hunter["catches"] += 1
    hunter["today"] += 1
    hunter["points"] += points
    best = by_id.get(hunter["best"]) if hunter["best"] else None
    if best is None or rarity_rank(bug["rarity"]) > rarity_rank(best["rarity"]):
        hunter["best"] = bug["id"]

    state["recent"].insert(0, {"login": login, "bug": bug["id"], "at": when_iso, "issue": issue})
    del state["recent"][RECENT_KEEP:]

    return {"status": "caught", "bug": bug, "points": points, "first_ever": first_ever,
            "hunter": dict(hunter)}


def mark_processed(state: dict, issue: int) -> None:
    if issue not in state["processed"]:
        state["processed"].append(issue)
        del state["processed"][:-PROCESSED_KEEP]


def leaderboard(state: dict, n: int = 5) -> list[tuple[str, dict]]:
    rows = list(state["hunters"].items())
    rows.sort(key=lambda kv: (-kv[1]["points"], -kv[1]["catches"], kv[0].lower()))
    return rows[:n]


def discovered(state: dict) -> int:
    return sum(1 for c in state["counts"].values() if c > 0)
