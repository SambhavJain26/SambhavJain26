"""Bug Hunt runner, called by .github/workflows/bug-hunt.yml.

  python -m game.play process   # read open bughunt issues + new comments, update state.json + README.md, write the outbox
  python -m game.play deliver   # post the outbox replies and close finished hunts (after the push)
  python -m game.play simulate --n 30 --seed 7 --out _preview   # local preview only

Security notes:
- Issue titles, comments and logins are untrusted. They never reach a shell: `gh` is
  called with an argument list (no shell=True), titles must match a fixed pattern,
  only the hunt starter's comments count, and an answer must be a single letter
  A-D or a line number.
- Only issues whose title starts with "bughunt" are touched.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import engine, render

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "game" / "bugs.json"
CHALLENGES_PATH = ROOT / "game" / "challenges.json"
STATE_PATH = ROOT / "game" / "state.json"
README_PATH = ROOT / "README.md"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_data() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def load_challenges() -> dict:
    return json.loads(CHALLENGES_PATH.read_text(encoding="utf-8"))


def load_state(data: dict, path: Path = STATE_PATH) -> dict:
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("version") == 3:
            for bug in data["bugs"]:
                state["counts"].setdefault(bug["id"], 0)
            return state
    return engine.initial_state(data["bugs"])


def save_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def outbox_path() -> Path:
    base = os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()
    return Path(os.environ.get("BUGHUNT_OUTBOX", Path(base) / "bughunt-outbox.json"))


def gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return result.stdout


def fetch_open_issues(repo: str) -> list[dict]:
    out = gh("issue", "list", "--repo", repo, "--state", "open", "--limit", "100",
             "--json", "number,title,author,createdAt")
    return sorted(json.loads(out), key=lambda i: i["number"])


def fetch_comments(repo: str, number: int) -> list[dict]:
    out = gh("issue", "view", str(number), "--repo", repo, "--json", "comments")
    return json.loads(out).get("comments", [])


def process(issues: list[dict], comments_for, state: dict, data: dict, challenges: dict,
            rng: random.Random, now: datetime) -> list[dict]:
    """Apply open bughunt issues (and their new comments) to `state`. Returns the outbox."""
    outbox = []
    for issue in issues:
        number = issue.get("number")
        kind = engine.classify_title(issue.get("title"))
        login = (issue.get("author") or {}).get("login")
        if kind is None or not isinstance(number, int):
            continue  # not a Bug Hunt issue: leave it alone
        if kind == "unknown" or not engine.valid_login(login):
            if number not in state["processed"]:
                engine.mark_processed(state, number)
                outbox.append({"issue": number, "body": render.reply_unknown(), "close": True})
            continue
        if str(number) not in state["encounters"]:
            if number in state["processed"]:
                outbox.append({"issue": number, "body": None, "close": True})  # finished earlier; just close
                continue
            when = issue.get("createdAt") or now.isoformat()
            result = engine.start_encounter(state, data, challenges, login, when, number, rng)
            if result["status"] == "encounter":
                outbox.append({"issue": number, "body": render.reply_encounter(result, data), "close": False})
            elif result["status"] == "limit":
                outbox.append({"issue": number, "body": render.reply_limit(result), "close": True})
            continue
        for c in sorted(comments_for(number), key=lambda c: c.get("createdAt", "")):
            author = (c.get("author") or {}).get("login")
            result = engine.answer_encounter(state, data, challenges, number, str(c.get("id")), author,
                                             c.get("body"), c.get("createdAt") or now.isoformat())
            if result is None:
                continue
            done = result["status"] in ("caught", "escaped")
            outbox.append({"issue": number, "body": render.reply_for_answer(result, data), "close": done})
            if done:
                break
    for number in engine.expire_encounters(state, now):
        outbox.append({"issue": number, "body": render.reply_expired(), "close": True})
    return outbox


def update_readme(state: dict, data: dict, readme_path: Path = README_PATH) -> None:
    readme = readme_path.read_text(encoding="utf-8")
    readme_path.write_text(render.replace_section(readme, render.section(state, data)),
                           encoding="utf-8", newline="\n")


def cmd_process() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    data, challenges = load_data(), load_challenges()
    state = load_state(data)
    before = json.dumps(state, sort_keys=True)
    outbox = process(fetch_open_issues(repo), lambda n: fetch_comments(repo, n), state, data, challenges,
                     random.SystemRandom(), now_utc())
    save_json(outbox_path(), {"repo": repo, "items": outbox})
    if json.dumps(state, sort_keys=True) != before or not STATE_PATH.exists():
        save_json(STATE_PATH, state)
        update_readme(state, data)
    print(f"queued {len(outbox)} Bug Hunt action(s)")
    return 0


def cmd_deliver() -> int:
    path = outbox_path()
    if not path.exists():
        print("no outbox")
        return 0
    box = json.loads(path.read_text(encoding="utf-8"))
    failures = 0
    for item in box["items"]:
        number = str(int(item["issue"]))
        try:
            if item.get("body"):
                with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
                    f.write(item["body"])
                    body_file = f.name
                try:
                    gh("issue", "comment", number, "--repo", box["repo"], "--body-file", body_file)
                finally:
                    os.unlink(body_file)
            if item.get("close"):
                gh("issue", "close", number, "--repo", box["repo"], "--reason", "completed")
        except subprocess.CalledProcessError as exc:
            failures += 1
            print(f"could not update #{number}: {exc.stderr.strip()}", file=sys.stderr)
    print(f"delivered {len(box['items']) - failures}/{len(box['items'])} actions")
    return 1 if failures else 0


def cmd_simulate(n: int, seed: int, out: Path) -> int:
    """Fill a throwaway copy of the state + README with fake hunts, for previewing only."""
    data, challenges = load_data(), load_challenges()
    rng = random.Random(seed)
    state = engine.initial_state(data["bugs"])
    hunters = ["octo-dev", "bugbuster", "null-ninja", "semi-colon", "heap-hero", "ada-l"]
    start = datetime(2026, 11, 14, tzinfo=timezone.utc)
    for i in range(n):
        when = (start + timedelta(hours=i * 2)).isoformat()
        who = rng.choice(hunters)
        r = engine.start_encounter(state, data, challenges, who, when, i + 1, rng)
        if r["status"] != "encounter":
            continue
        ch = r["challenge"]
        for attempt in range(engine.MAX_TRIES):
            if r["mode"] == "report":
                good = engine.LETTERS[r["options"].index(ch["bug"])]
                ans = good if rng.random() < 0.55 else rng.choice(engine.LETTERS)
            else:
                ans = str(ch["answer"][0] if rng.random() < 0.45 else rng.randint(1, len(ch["lines"])))
            res = engine.answer_encounter(state, data, challenges, i + 1, f"c{i}-{attempt}", who, ans, when)
            if res and res["status"] in ("caught", "escaped"):
                break
    out.mkdir(parents=True, exist_ok=True)
    save_json(out / "state.json", state)
    readme = README_PATH.read_text(encoding="utf-8")
    (out / "README.md").write_text(render.replace_section(readme, render.section(state, data)),
                                   encoding="utf-8", newline="\n")
    print(f"simulated {n} hunts into {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="game.play")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("process")
    sub.add_parser("deliver")
    sim = sub.add_parser("simulate")
    sim.add_argument("--n", type=int, default=30)
    sim.add_argument("--seed", type=int, default=7)
    sim.add_argument("--out", type=Path, default=ROOT / "_preview")
    args = parser.parse_args(argv)
    if args.cmd == "process":
        return cmd_process()
    if args.cmd == "deliver":
        return cmd_deliver()
    return cmd_simulate(args.n, args.seed, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
