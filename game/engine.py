"""Bug Hunt: pure game logic (no I/O, no network). Easy to unit-test.

Luck finds the bug, skill catches it:
  1. A visitor opens an issue titled "bughunt: catch".
  2. The bot rolls a bug, weighted by rarity (luck), and serves that bug's challenge,
     either a bug report (pick A-D) or a code snippet (pick the line, double points).
  3. The visitor answers by commenting with just the letter or the line number.
  4. Right answer: the bug is caught. Wrong: a hint, up to MAX_TRIES tries.
     The issue closes when the bug is caught, escapes, or is left alone for a day.
"""
from __future__ import annotations

import random
import re
from datetime import datetime, timedelta
from typing import Any

CATCH_RE = re.compile(r"^\s*bughunt\s*:\s*catch\s*$", re.IGNORECASE)
ANSWER_RE = re.compile(r"^\s*([a-d]|\d{1,2})\s*[.)]?\s*$", re.IGNORECASE)
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")

MODES = ("report", "code")
LETTERS = "ABCD"
MAX_TRIES = 3
DAILY_LIMIT = 10
CODE_MULTIPLIER = 2
DISCOVERER_BONUS = 3
ENCOUNTER_TTL = timedelta(hours=24)
RECENT_KEEP = 8
PROCESSED_KEEP = 500
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]


# ------------------------------------------------------------------ input checks
def classify_title(title: Any) -> str | None:
    """'catch' for a new encounter, 'unknown' for other bughunt titles, None for unrelated issues."""
    if not isinstance(title, str) or len(title) > 200:
        return None
    if CATCH_RE.match(title):
        return "catch"
    if title.strip().lower().startswith("bughunt"):
        return "unknown"
    return None


def parse_answer(body: Any) -> str | None:
    """A single letter A-D or a line number, nothing else. Returns it upper-cased, or None."""
    if not isinstance(body, str) or len(body) > 20:
        return None
    m = ANSWER_RE.match(body)
    return m.group(1).upper() if m else None


def valid_login(login: Any) -> bool:
    return isinstance(login, str) and bool(LOGIN_RE.match(login)) and not login.endswith("-")


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


# ------------------------------------------------------------------ state
def initial_state(bugs: list[dict]) -> dict:
    return {"version": 3, "total": 0, "counts": {b["id"]: 0 for b in bugs},
            "hunters": {}, "recent": [], "processed": [], "encounters": {}}


def mark_processed(state: dict, issue: int) -> None:
    if issue not in state["processed"]:
        state["processed"].append(issue)
        del state["processed"][:-PROCESSED_KEEP]


def rarity_rank(rarity: str) -> int:
    return RARITY_ORDER.index(rarity)


def challenge_for(challenges: dict, mode: str, bug_id: str) -> dict:
    return next(c for c in challenges[mode] if c["bug"] == bug_id)


def _hunter(state: dict, login: str, day: str) -> dict:
    h = state["hunters"].setdefault(login, {"catches": 0, "points": 0, "best": None, "day": day, "today": 0})
    if h["day"] != day:
        h["day"], h["today"] = day, 0
    return h


# ------------------------------------------------------------------ playing
def start_encounter(state: dict, data: dict, challenges: dict, login: str, when_iso: str,
                    issue: int, rng: random.Random) -> dict:
    """Roll a bug (luck) and pick its challenge. status: encounter, limit, duplicate."""
    if not valid_login(login):
        raise ValueError("invalid login")
    key = str(issue)
    if key in state["encounters"] or issue in state["processed"]:
        return {"status": "duplicate"}
    hunter = _hunter(state, login, when_iso[:10])
    if hunter["today"] >= DAILY_LIMIT:
        mark_processed(state, issue)
        return {"status": "limit", "limit": DAILY_LIMIT}
    hunter["today"] += 1

    bugs = data["bugs"]
    bug = rng.choices(bugs, weights=[float(b["weight"]) for b in bugs], k=1)[0]
    # The bot announces the rarity, so a bug that's alone in its rarity (the legendary one)
    # always comes as a code challenge: a multiple-choice report would give it away.
    alone = sum(1 for b in bugs if b["rarity"] == bug["rarity"]) == 1
    mode = "code" if alone else rng.choice(MODES)
    ch = challenge_for(challenges, mode, bug["id"])
    enc = {"login": login, "bug": bug["id"], "mode": mode, "cid": ch["id"],
           "tries": 0, "opened": when_iso, "seen": []}
    if mode == "report":
        enc["options"] = report_options(bugs, bug, rng)
    state["encounters"][key] = enc
    return {"status": "encounter", "bug": bug, "mode": mode, "challenge": ch, "options": enc.get("options")}


def report_options(bugs: list[dict], bug: dict, rng: random.Random) -> list[str]:
    """The right bug plus 3 decoys, preferring the same rarity so the announced rarity
    doesn't reveal the answer; topped up from the nearest rarities if needed."""
    rank = rarity_rank(bug["rarity"])
    others = [b for b in bugs if b["id"] != bug["id"]]
    rng.shuffle(others)
    others.sort(key=lambda b: abs(rarity_rank(b["rarity"]) - rank))
    options = [bug["id"]] + [b["id"] for b in others[:len(LETTERS) - 1]]
    rng.shuffle(options)
    return options


def is_correct(enc: dict, ch: dict, answer: str) -> bool:
    if enc["mode"] == "report":
        return answer in LETTERS and enc["options"][LETTERS.index(answer)] == ch["bug"]
    return answer.isdigit() and int(answer) in ch["answer"]


def valid_option(enc: dict, ch: dict, answer: str) -> bool:
    if enc["mode"] == "report":
        return answer in LETTERS[:len(enc["options"])]
    return answer.isdigit() and 1 <= int(answer) <= len(ch["lines"])


def answer_encounter(state: dict, data: dict, challenges: dict, issue: int, comment_id: str,
                     login: str, body: str, when_iso: str) -> dict | None:
    """Judge one comment on an open encounter. Returns None for comments to ignore.
    status: caught, wrong, escaped, invalid."""
    enc = state["encounters"].get(str(issue))
    if enc is None or login != enc["login"] or comment_id in enc["seen"]:
        return None
    enc["seen"].append(comment_id)
    answer = parse_answer(body)
    if answer is None:
        return None  # chatter, not an answer: stay quiet
    ch = next(c for c in challenges[enc["mode"]] if c["id"] == enc["cid"])
    if not valid_option(enc, ch, answer):
        return {"status": "invalid", "encounter": enc, "challenge": ch}

    bugs = {b["id"]: b for b in data["bugs"]}
    bug = bugs[enc["bug"]]
    if not is_correct(enc, ch, answer):
        enc["tries"] += 1
        left = MAX_TRIES - enc["tries"]
        if left > 0:
            return {"status": "wrong", "encounter": enc, "challenge": ch, "tries_left": left}
        del state["encounters"][str(issue)]
        mark_processed(state, issue)
        return {"status": "escaped", "challenge": ch, "bug": bug}

    points = data["rarities"][bug["rarity"]]["points"] * (CODE_MULTIPLIER if enc["mode"] == "code" else 1)
    first_ever = state["counts"].get(bug["id"], 0) == 0
    if first_ever:
        points += DISCOVERER_BONUS
    hunter = _hunter(state, login, when_iso[:10])
    state["counts"][bug["id"]] = state["counts"].get(bug["id"], 0) + 1
    state["total"] += 1
    hunter["catches"] += 1
    hunter["points"] += points
    best = bugs.get(hunter["best"]) if hunter["best"] else None
    if best is None or rarity_rank(bug["rarity"]) > rarity_rank(best["rarity"]):
        hunter["best"] = bug["id"]
    state["recent"].insert(0, {"login": login, "bug": bug["id"], "at": when_iso, "issue": issue, "mode": enc["mode"]})
    del state["recent"][RECENT_KEEP:]
    mode = enc["mode"]
    del state["encounters"][str(issue)]
    mark_processed(state, issue)
    return {"status": "caught", "challenge": ch, "bug": bug, "points": points, "mode": mode,
            "first_ever": first_ever, "hunter": dict(hunter)}


def expire_encounters(state: dict, now: datetime) -> list[int]:
    """Close encounters nobody answered within ENCOUNTER_TTL. Returns their issue numbers."""
    gone = [int(k) for k, e in state["encounters"].items() if now - _ts(e["opened"]) > ENCOUNTER_TTL]
    for n in gone:
        del state["encounters"][str(n)]
        mark_processed(state, n)
    return gone


def leaderboard(state: dict, n: int = 5) -> list[tuple[str, dict]]:
    rows = [r for r in state["hunters"].items() if r[1]["catches"] > 0]
    rows.sort(key=lambda kv: (-kv[1]["points"], -kv[1]["catches"], kv[0].lower()))
    return rows[:n]


def discovered(state: dict) -> int:
    return sum(1 for c in state["counts"].values() if c > 0)
