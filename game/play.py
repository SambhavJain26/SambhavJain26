"""Bug Hunt leaderboard runner, called by .github/workflows/bug-hunt.yml.

  python -m game.play process   # read open bughunt issues, update state.json + README.md, write the outbox
  python -m game.play deliver   # post the outbox replies and close those issues (after the push)
  python -m game.play simulate --n 30 --seed 7 --out _preview   # local preview only

Security notes:
- Issue titles and logins are untrusted. They never reach a shell: `gh` is called
  with an argument list (no shell=True), titles must match a fixed pattern, the
  bug id must exist in bugs.json, and logins are validated before use.
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
STATE_PATH = ROOT / "game" / "state.json"
README_PATH = ROOT / "README.md"


def load_data() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def load_state(data: dict, path: Path = STATE_PATH) -> dict:
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("version") in (4, engine.STATE_VERSION):
            engine.migrate(state, data)
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


def process(issues: list[dict], state: dict, data: dict, now: datetime) -> list[dict]:
    """Apply open bughunt issues to `state`; return the replies to post (every one closes its issue)."""
    outbox = []
    for issue in issues:
        number = issue.get("number")
        parsed = engine.parse_title(issue.get("title"))
        login = (issue.get("author") or {}).get("login")
        if parsed is None or not isinstance(number, int):
            continue  # not a Bug Hunt issue: leave it alone
        if number in state["processed"]:
            outbox.append({"issue": number, "body": None})  # handled before; just close it
            continue
        if parsed["kind"] == "legacy":
            engine.mark_processed(state, number)
            outbox.append({"issue": number, "body": render.reply_legacy()})
            continue
        if parsed["kind"] == "unknown" or not engine.valid_login(login):
            engine.mark_processed(state, number)
            outbox.append({"issue": number, "body": render.reply_unknown()})
            continue
        when = issue.get("createdAt") or now.isoformat()
        result = engine.record_batch(state, data, login, when, number, parsed["entries"])
        outbox.append({"issue": number, "body": render.reply_for(result, data)})
    return outbox


def update_readme(state: dict, data: dict, readme_path: Path = README_PATH) -> None:
    readme = readme_path.read_text(encoding="utf-8")
    readme_path.write_text(render.replace_section(readme, render.section(state, data)),
                           encoding="utf-8", newline="\n")


def cmd_process() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    data = load_data()
    state = load_state(data)
    before = json.dumps(state, sort_keys=True)
    outbox = process(fetch_open_issues(repo), state, data, datetime.now(timezone.utc))
    save_json(outbox_path(), {"repo": repo, "items": outbox})
    if json.dumps(state, sort_keys=True) != before or not STATE_PATH.exists():
        save_json(STATE_PATH, state)
        update_readme(state, data)
    print(f"queued {len(outbox)} Bug Hunt repl(ies)")
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
            gh("issue", "close", number, "--repo", box["repo"], "--reason", "completed")
        except subprocess.CalledProcessError as exc:
            failures += 1
            print(f"could not update #{number}: {exc.stderr.strip()}", file=sys.stderr)
    print(f"delivered {len(box['items']) - failures}/{len(box['items'])}")
    return 1 if failures else 0


def cmd_simulate(n: int, seed: int, out: Path) -> int:
    """Fill a throwaway copy of the state + README with fake leaderboard entries, for previewing only."""
    data = load_data()
    rng = random.Random(seed)
    state = engine.initial_state(data["bugs"])
    hunters = ["octo-dev", "bugbuster", "null-ninja", "semi-colon", "heap-hero", "ada-l"]
    start = datetime(2026, 11, 14, tzinfo=timezone.utc)
    bugs = data["bugs"]
    for i in range(n):
        bug = rng.choices(bugs, weights=[float(b["weight"]) for b in bugs], k=1)[0]
        engine.record_catch(state, data, rng.choice(hunters), (start + timedelta(hours=i * 3)).isoformat(),
                            i + 1, bug["id"], rng.choice(["report", "code"]))
    out.mkdir(parents=True, exist_ok=True)
    save_json(out / "state.json", state)
    readme = README_PATH.read_text(encoding="utf-8")
    (out / "README.md").write_text(render.replace_section(readme, render.section(state, data)),
                                   encoding="utf-8", newline="\n")
    print(f"simulated {n} leaderboard entries into {out}")
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
