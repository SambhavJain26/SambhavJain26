"""Bug Hunt: turn leaderboard state into README markdown and issue replies (pure functions)."""
from __future__ import annotations

from datetime import datetime

from . import engine

OWNER = "SambhavJain26"
REPO = "SambhavJain26"
BRANCH = "main"
PROFILE_URL = f"https://github.com/{OWNER}"
BOARD_URL = f"{PROFILE_URL}#bug-hunt"
GAME_URL = f"https://{OWNER.lower()}.github.io/{REPO}/"
RAW_BASE = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}"

START = "<!-- BUGHUNT:START -->"
END = "<!-- BUGHUNT:END -->"


def _pic(path_light: str, path_dark: str, width: int, alt: str) -> str:
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{path_dark}">'
            f'<img src="{path_light}" width="{width}" alt="{alt}"></picture>')


def _date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%b %d").replace(" 0", " ")
    except ValueError:
        return iso[:10]


# ------------------------------------------------------------------ README section
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
            img = _pic(f"game/art/unknown-{bug['rarity']}-light.svg", f"game/art/unknown-{bug['rarity']}-dark.svg",
                       112, "Undiscovered bug")
            caption = f"<sub><b>???</b></sub><br><sub>{rarity} · not caught yet</sub>"
        cells.append(f'<td align="center" width="{100 // per_row}%">{img}<br>{caption}</td>')
    rows = ["<tr>" + "".join(cells[i:i + per_row]) + "</tr>" for i in range(0, len(cells), per_row)]
    return '<table align="center">\n' + "\n".join(rows) + "\n</table>"


def side_tables(state: dict, data: dict) -> str:
    by_id = {b["id"]: b for b in data["bugs"]}
    rarities = data["rarities"]
    medals = ["🥇", "🥈", "🥉", "4.", "5."]
    top = "<br>".join(
        f'{medals[i]} <a href="https://github.com/{login}">@{login}</a> · <b>{h["points"]}</b> pts · {h["catches"]} caught'
        for i, (login, h) in enumerate(engine.leaderboard(state, 5)))
    recent = "<br>".join(
        f'{rarities[by_id[r["bug"]]["rarity"]]["emoji"]} <a href="https://github.com/{r["login"]}">@{r["login"]}</a> '
        f'caught <b>{by_id[r["bug"]]["name"]}</b> <sub>{_date(r["at"])}</sub>'
        for r in state["recent"][:5] if r["bug"] in by_id)
    return ('<table align="center"><tr>'
            f'<td valign="top" width="50%"><b>🏆 Top hunters</b><br><br>{top}</td>'
            f'<td valign="top" width="50%"><b>🕘 Latest catches</b><br><br>{recent}</td>'
            '</tr></table>')


def section(state: dict, data: dict) -> str:
    button = _pic("assets/catch-button-light.svg", "assets/catch-button-dark.svg", 330, "Catch a bug")
    total = len(data["bugs"])
    if state["total"]:
        board = side_tables(state, data)
        footer = (f'<p align="center"><sub>Community catches: <b>{state["total"]}</b> · Bugs discovered: '
                  f'<b>{engine.discovered(state)} / {total}</b></sub></p>')
    else:
        board = '<p align="center"><b>No hunters on the board yet. Be the first!</b></p>'
        footer = ""
    return "\n".join([
        START,
        f'<p align="center"><a href="{GAME_URL}">{button}</a></p>',
        '<p align="center"><sub>Opens the game: 🎲 luck finds the bug, 🧠 skill catches it, instantly.<br>'
        'Caught one? Add yourself to the board below from the game.</sub></p>',
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


# ------------------------------------------------------------------ issue replies
BACK = f"[See the leaderboard →]({BOARD_URL}) · [Play again]({GAME_URL})"


def reply_recorded(result: dict, data: dict) -> str:
    bug = result["bug"]
    rarity = data["rarities"][bug["rarity"]]
    h = result["hunter"]
    extras = []
    if result["mode"] == "code":
        extras.append("double points for code")
    if result["first_ever"]:
        extras.append(f"+{engine.DISCOVERER_BONUS} for the first catch on the board")
    lines = [
        f"## 🏆 You're on the board! **{bug['name']}** recorded",
        "",
        f'<img src="{RAW_BASE}/game/art/{bug["id"]}-light.svg" width="140" alt="{bug["name"]}">',
        "",
        f"{rarity['emoji']} **{rarity['label']}** · **+{result['points']} pts**" + (f" ({', '.join(extras)})" if extras else ""),
        "",
    ]
    if result["first_ever"]:
        lines += ["✨ **First ever on the board!** It's now unlocked in the profile's Bugdex.", ""]
    lines += [f"Your totals on the board: **{h['catches']}** caught · **{h['points']}** pts.", "", BACK]
    return "\n".join(lines)


def reply_unknown_bug() -> str:
    return f"🤔 That bug isn't in the Bugdex. Use the **Add me to the leaderboard** button in the game.\n\n{BACK}"


def reply_limit(result: dict) -> str:
    return f"😴 You've added {result['limit']} catches today (UTC). Come back tomorrow!\n\n{BACK}"


def reply_legacy() -> str:
    return (f"🐛 Bug Hunt has moved to an instant game: no waiting for a bot. "
            f"[Play it here]({GAME_URL}).\n\n{BACK}")


def reply_unknown() -> str:
    return f"🤔 I couldn't read that title. Play at [the Bug Hunt page]({GAME_URL}) and add catches from there.\n\n{BACK}"


def reply_for(result: dict, data: dict) -> str:
    status = result["status"]
    if status == "recorded":
        return reply_recorded(result, data)
    if status == "unknown_bug":
        return reply_unknown_bug()
    if status == "limit":
        return reply_limit(result)
    return f"This one was already counted. 👍\n\n{BACK}"
