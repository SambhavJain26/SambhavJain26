"""Bug Hunt: turn game state into README markdown and issue replies (pure functions)."""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from . import engine

OWNER = "SambhavJain26"
REPO = "SambhavJain26"
BRANCH = "main"
PROFILE_URL = f"https://github.com/{OWNER}"
RAW_BASE = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}"

START = "<!-- BUGHUNT:START -->"
END = "<!-- BUGHUNT:END -->"

ISSUE_BODY = ("Just press **Create** without changing the title. "
              "A bot will reply with the bug you caught in about a minute, then close this issue. 🐛")
CATCH_URL = (f"https://github.com/{OWNER}/{REPO}/issues/new"
             f"?title={quote('bughunt: catch')}&body={quote(ISSUE_BODY)}")


def _pic(path_light: str, path_dark: str, width: int, alt: str) -> str:
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{path_dark}">'
            f'<img src="{path_light}" width="{width}" alt="{alt}"></picture>')


def _date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%b %d").replace(" 0", " ")
    except ValueError:
        return iso[:10]


def bugdex_table(state: dict, data: dict, per_row: int = 4) -> str:
    rarities = data["rarities"]
    cells = []
    for bug in data["bugs"]:
        n = state["counts"].get(bug["id"], 0)
        rarity = rarities[bug["rarity"]]["label"]
        if n:
            img = _pic(f"game/art/{bug['id']}-light.svg", f"game/art/{bug['id']}-dark.svg", 112, bug["name"])
            caption = f"<sub><b>{bug['name']}</b></sub><br><sub>{rarity} · ×{n}</sub>"
        else:
            img = _pic(f"game/art/unknown-{bug['rarity']}-light.svg", f"game/art/unknown-{bug['rarity']}-dark.svg", 112, "Undiscovered bug")
            caption = f"<sub><b>???</b></sub><br><sub>{rarity} · not caught yet</sub>"
        cells.append(f'<td align="center" width="{100 // per_row}%">{img}<br>{caption}</td>')
    rows = ["<tr>" + "".join(cells[i:i + per_row]) + "</tr>" for i in range(0, len(cells), per_row)]
    return '<table align="center">\n' + "\n".join(rows) + "\n</table>"


def side_tables(state: dict, data: dict) -> str:
    by_id = {b["id"]: b for b in data["bugs"]}
    rarities = data["rarities"]
    medals = ["🥇", "🥈", "🥉", "4.", "5."]
    lb = engine.leaderboard(state, 5)
    if lb:
        top = "<br>".join(
            f'{medals[i]} <a href="https://github.com/{login}">@{login}</a> · <b>{h["points"]}</b> pts · {h["catches"]} caught'
            for i, (login, h) in enumerate(lb))
    else:
        top = "<i>No hunters yet. Be the first!</i>"
    if state["recent"]:
        recent = "<br>".join(
            f'{rarities[by_id[r["bug"]]["rarity"]]["emoji"]} <a href="https://github.com/{r["login"]}">@{r["login"]}</a> '
            f'caught <b>{by_id[r["bug"]]["name"]}</b> <sub>{_date(r["at"])}</sub>'
            for r in state["recent"][:5] if r["bug"] in by_id)
    else:
        recent = "<i>The bugs are waiting…</i>"
    return ('<table align="center"><tr>'
            f'<td valign="top" width="50%"><b>🏆 Top hunters</b><br><br>{top}</td>'
            f'<td valign="top" width="50%"><b>🕘 Latest catches</b><br><br>{recent}</td>'
            '</tr></table>')


def section(state: dict, data: dict) -> str:
    button = _pic("assets/catch-button-light.svg", "assets/catch-button-dark.svg", 330, "Catch a bug")
    total = len(data["bugs"])
    if state["total"]:
        # The leaderboard and recent catches only appear once someone has played.
        board = side_tables(state, data)
        footer = (f'<p align="center"><sub>Total catches: <b>{state["total"]}</b> · Bugs discovered: '
                  f'<b>{engine.discovered(state)} / {total}</b> · Up to {engine.DAILY_LIMIT} catches per hunter per day</sub></p>')
    else:
        board = '<p align="center"><b>No hunters yet. Be the first to catch one!</b></p>'
        footer = ""
    return "\n".join([
        START,
        f'<p align="center"><a href="{CATCH_URL}">{button}</a></p>',
        '<p align="center"><sub>Opens a pre-filled issue. Press <b>Create</b> and a bot replies with your catch in about a minute.</sub></p>',
        "",
        bugdex_table(state, data),
        "",
        board,
        "",
        footer,
        END,
    ])


def replace_section(readme: str, new_section: str) -> str:
    start, end = readme.find(START), readme.find(END)
    if start == -1 or end == -1 or end < start:
        raise ValueError("Bug Hunt markers not found in README")
    return readme[:start] + new_section + readme[end + len(END):]


# ---------------------------------------------------------------- issue replies
def reply_caught(result: dict, data: dict) -> str:
    bug = result["bug"]
    rarity = data["rarities"][bug["rarity"]]
    h = result["hunter"]
    lines = [
        f"## 🎣 You caught **{bug['name']}**!",
        "",
        f'<img src="{RAW_BASE}/game/art/{bug["id"]}-light.svg" width="160" alt="{bug["name"]}">',
        "",
        f"{rarity['emoji']} **{rarity['label']}** · +{result['points']} pts",
        "",
        f"> {bug['flavor']}",
        "",
    ]
    if result.get("first_ever"):
        lines += ["✨ **First ever catch of this bug!** It's now unlocked in the Bugdex.", ""]
    lines += [
        f"Your totals: **{h['catches']}** caught · **{h['points']}** pts · {h['today']}/{engine.DAILY_LIMIT} today.",
        "",
        f"[Back to the profile →]({PROFILE_URL}) · [Catch another]({CATCH_URL})",
    ]
    return "\n".join(lines)


def reply_limit(result: dict) -> str:
    return (f"😴 Your net needs a rest: you've made {result['limit']} catches today (UTC). "
            f"Come back tomorrow!\n\n[Back to the profile →]({PROFILE_URL})")


def reply_unknown() -> str:
    return ("🤔 I only understand one command: an issue titled exactly `bughunt: catch`.\n\n"
            f"[Try again with the button]({CATCH_URL}) · [Back to the profile →]({PROFILE_URL})")


def reply_duplicate() -> str:
    return f"This catch was already counted. 👍\n\n[Back to the profile →]({PROFILE_URL})"
