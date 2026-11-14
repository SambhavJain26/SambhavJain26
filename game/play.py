"""Bug Hunt runner, called by .github/workflows/bug-hunt.yml.

  python -m game.play process   # read open issues, update state.json + README.md, write the outbox
  python -m game.play deliver   # post the outbox replies and close those issues (after the push)
  python -m game.play simulate --n 30 --seed 7 --out _preview   # local preview only

Security notes:
- Issue titles and logins are untrusted. They never reach a shell: `gh` is called
  with an argument list (no shell=True), titles are only matched against a strict
  regex, and logins are validated before use.
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
    issues = json.loads(out)
    return sorted(issues, key=lambda i: i["number"])


def process_issues(issues: list[dict], state: dict, data: dict, rng: random.Random) -> list[dict]:
    """Apply every bughunt issue to `state`; return the replies to post (the outbox)."""
    outbox = []
    for issue in issues:
        number = issue.get("number")
        kind = engine.classify_title(issue.get("title"))
        login = (issue.get("author") or {}).get("login")
        if kind is None or not isinstance(number, int):
            continue  # not a Bug Hunt issue: leave it alone
        if not engine.valid_login(login):
            engine.mark_processed(state, number)
            outbox.append({"issue": number, "body": render.reply_unknown()})
            continue
        if kind == "unknown":
            engine.mark_processed(state, number)
            outbox.append({"issue": number, "body": render.reply_unknown()})
            continue
        when = issue.get("createdAt") or datetime.now(timezone.utc).isoformat()
        result = engine.apply_catch(state, data, login, when, number, rng)
        if result["status"] == "caught":
            body = render.reply_caught(result, data)
        elif result["status"] == "limit":
            body = render.reply_limit(result)
        else:
            body = render.reply_duplicate()
        outbox.append({"issue": number, "body": body})
    return outbox


def update_readme(state: dict, data: dict, readme_path: Path = README_PATH) -> None:
    readme = readme_path.read_text(encoding="utf-8")
    readme_path.write_text(render.replace_section(readme, render.section(state, data)),
                           encoding="utf-8", newline="\n")


def cmd_process() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    data = load_data()
    state = load_state(data)
    issues = fetch_open_issues(repo)
    outbox = process_issues(issues, state, data, random.SystemRandom())
    save_json(outbox_path(), {"repo": repo, "items": outbox})
    if outbox:
        save_json(STATE_PATH, state)
        update_readme(state, data)
    print(f"processed {len(outbox)} Bug Hunt issue(s)")
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
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(item["body"])
            body_file = f.name
        try:
            gh("issue", "comment", number, "--repo", box["repo"], "--body-file", body_file)
            gh("issue", "close", number, "--repo", box["repo"], "--reason", "completed")
        except subprocess.CalledProcessError as exc:
            failures += 1
            print(f"could not reply to #{number}: {exc.stderr.strip()}", file=sys.stderr)
        finally:
            os.unlink(body_file)
    print(f"delivered {len(box['items']) - failures}/{len(box['items'])} replies")
    return 1 if failures else 0


def cmd_simulate(n: int, seed: int, out: Path) -> int:
    """Fill a throwaway copy of the state + README with fake catches, for previewing only."""
    data = load_data()
    rng = random.Random(seed)
    state = engine.initial_state(data["bugs"])
    hunters = ["octo-dev", "bugbuster", "null-ninja", "semi-colon", "heap-hero", "ada-l"]
    start = datetime(2026, 11, 14, tzinfo=timezone.utc)
    issues = [{"number": i + 1, "title": "bughunt: catch", "author": {"login": rng.choice(hunters)},
               "createdAt": (start + timedelta(hours=i)).isoformat()} for i in range(n)]
    process_issues(issues, state, data, rng)
    out.mkdir(parents=True, exist_ok=True)
    save_json(out / "state.json", state)
    readme = README_PATH.read_text(encoding="utf-8")
    (out / "README.md").write_text(render.replace_section(readme, render.section(state, data)),
                                   encoding="utf-8", newline="\n")
    print(f"simulated {n} catches into {out}")
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
