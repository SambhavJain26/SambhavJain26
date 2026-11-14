"""Bug Hunt: pure game logic (no I/O, no network). Easy to unit-test.

Two challenges are live at any time:
  report  a short bug report; the player picks which bug caused it   (easier)
  code    a short snippet; the player picks the line with the bug    (double points)

A correct answer catches that challenge's bug. Each player gets 3 tries per
challenge. A challenge rotates after 3 people solve it, or once a day.

Issue titles (the only player input):
  bughunt: report <challenge id> <bug id>      e.g. bughunt: report r08 timezone-bug
  bughunt: code   <challenge id> <line>        e.g. bughunt: code c05 3
"""
from __future__ import annotations

import re
from typing import Any

TITLE_PREFIX = "bughunt"
ANSWER_RE = re.compile(r"^\s*bughunt\s*:\s*(report|code)\s+([a-z]\d{2})\s+([a-z0-9-]{1,40})\s*$", re.IGNORECASE)
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")

MODES = ("report", "code")
MAX_TRIES = 3
SOLVES_TO_ROTATE = 3
DAILY_LIMIT = 15
FIRST_SOLVER_BONUS = 3
CODE_MULTIPLIER = 2
RECENT_KEEP = 8
PROCESSED_KEEP = 500
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]
START_INDEX = {"report": 0, "code": 4}


# ------------------------------------------------------------------ input checks
def parse_title(title: Any) -> dict | None:
    """{'kind': 'answer', mode, cid, answer} for a well-formed answer,
    {'kind': 'unknown'} for other bughunt titles, None for unrelated issues."""
    if not isinstance(title, str) or len(title) > 200:
        return None
    m = ANSWER_RE.match(title)
    if m:
        return {"kind": "answer", "mode": m.group(1).lower(), "cid": m.group(2).lower(),
                "answer": m.group(3).lower()}
    if title.strip().lower().startswith(TITLE_PREFIX):
        return {"kind": "unknown"}
    return None


def valid_login(login: Any) -> bool:
    return isinstance(login, str) and bool(LOGIN_RE.match(login)) and not login.endswith("-")


# ------------------------------------------------------------------ state
def initial_state(bugs: list[dict], challenges: dict, today: str) -> dict:
    return {
        "version": 2,
        "total": 0,
        "counts": {b["id"]: 0 for b in bugs},
        "hunters": {},
        "recent": [],
        "processed": [],
        # The two modes start at different points so they never feature the same bug.
        "current": {mode: {"index": START_INDEX[mode], "id": challenges[mode][START_INDEX[mode]]["id"],
                           "since": today, "solvers": []} for mode in MODES},
        "tries": {},
    }


def challenge_by_id(challenges: dict, mode: str, cid: str) -> dict | None:
    return next((c for c in challenges[mode] if c["id"] == cid), None)


def current_challenge(state: dict, challenges: dict, mode: str) -> dict:
    return challenge_by_id(challenges, mode, state["current"][mode]["id"])


def is_correct(challenge: dict, mode: str, answer: str) -> bool:
    if mode == "report":
        return answer == challenge["bug"]
    return answer.isdigit() and int(answer) in challenge["answer"]


def valid_option(challenge: dict, mode: str, answer: str) -> bool:
    if mode == "report":
        return answer in challenge["options"]
    return answer.isdigit() and 1 <= int(answer) <= len(challenge["lines"])


def mark_processed(state: dict, issue: int) -> None:
    if issue not in state["processed"]:
        state["processed"].append(issue)
        del state["processed"][:-PROCESSED_KEEP]


def rarity_rank(rarity: str) -> int:
    return RARITY_ORDER.index(rarity)


# ------------------------------------------------------------------ playing
def apply_answer(state: dict, data: dict, challenges: dict, login: str, when_iso: str,
                 issue: int, mode: str, cid: str, answer: str) -> dict:
    """Apply one answer. result['status'] is one of:
    caught, wrong, out_of_tries, already_solved, stale, invalid_option, limit, duplicate."""
    if not valid_login(login):
        raise ValueError("invalid login")
    if issue in state["processed"]:
        return {"status": "duplicate"}
    mark_processed(state, issue)

    day = when_iso[:10]
    hunter = state["hunters"].setdefault(
        login, {"catches": 0, "points": 0, "best": None, "day": day, "today": 0})
    if hunter["day"] != day:
        hunter["day"], hunter["today"] = day, 0
    if hunter["today"] >= DAILY_LIMIT:
        return {"status": "limit", "limit": DAILY_LIMIT}

    live = state["current"][mode]
    if cid != live["id"]:
        return {"status": "stale"}
    challenge = current_challenge(state, challenges, mode)
    if not valid_option(challenge, mode, answer):
        return {"status": "invalid_option", "challenge": challenge}

    hunter["today"] += 1
    tries = state["tries"].setdefault(cid, {})
    if login in live["solvers"]:
        return {"status": "already_solved", "challenge": challenge}
    if tries.get(login, 0) >= MAX_TRIES:
        return {"status": "out_of_tries", "challenge": challenge}

    if not is_correct(challenge, mode, answer):
        tries[login] = tries.get(login, 0) + 1
        left = MAX_TRIES - tries[login]
        return {"status": "wrong" if left else "out_of_tries", "challenge": challenge, "tries_left": left}

    bugs = {b["id"]: b for b in data["bugs"]}
    bug = bugs[challenge["bug"]]
    points = data["rarities"][bug["rarity"]]["points"] * (CODE_MULTIPLIER if mode == "code" else 1)
    first_solver = not live["solvers"]
    if first_solver:
        points += FIRST_SOLVER_BONUS
    first_ever = state["counts"].get(bug["id"], 0) == 0

    live["solvers"].append(login)
    state["counts"][bug["id"]] = state["counts"].get(bug["id"], 0) + 1
    state["total"] += 1
    hunter["catches"] += 1
    hunter["points"] += points
    best = bugs.get(hunter["best"]) if hunter["best"] else None
    if best is None or rarity_rank(bug["rarity"]) > rarity_rank(best["rarity"]):
        hunter["best"] = bug["id"]
    state["recent"].insert(0, {"login": login, "bug": bug["id"], "at": when_iso, "issue": issue, "mode": mode})
    del state["recent"][RECENT_KEEP:]

    return {"status": "caught", "challenge": challenge, "bug": bug, "points": points,
            "first_solver": first_solver, "first_ever": first_ever, "mode": mode, "hunter": dict(hunter)}


def rotate_if_needed(state: dict, challenges: dict, today: str) -> list[str]:
    """Advance a mode to its next challenge after enough solves or a new day.
    Returns the modes that rotated."""
    rotated = []
    for mode in MODES:
        live = state["current"][mode]
        if len(live["solvers"]) >= SOLVES_TO_ROTATE or live["since"] < today:
            old = live["id"]
            nxt = (live["index"] + 1) % len(challenges[mode])
            state["current"][mode] = {"index": nxt, "id": challenges[mode][nxt]["id"], "since": today, "solvers": []}
            state["tries"].pop(old, None)
            rotated.append(mode)
    return rotated


def leaderboard(state: dict, n: int = 5) -> list[tuple[str, dict]]:
    rows = list(state["hunters"].items())
    rows = [r for r in rows if r[1]["catches"] > 0]
    rows.sort(key=lambda kv: (-kv[1]["points"], -kv[1]["catches"], kv[0].lower()))
    return rows[:n]


def discovered(state: dict) -> int:
    return sum(1 for c in state["counts"].values() if c > 0)
