"""Bug Hunt: turn game state into README markdown and issue replies (pure functions)."""
from __future__ import annotations

import html
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
              "A bot will check your answer in about a minute, reply here and close this issue. 🐛")


def answer_url(mode: str, cid: str, answer: str) -> str:
    title = f"bughunt: {mode} {cid} {answer}"
    return f"https://github.com/{OWNER}/{REPO}/issues/new?title={quote(title)}&body={quote(ISSUE_BODY)}"


def _pic(path_light: str, path_dark: str, width: int, alt: str) -> str:
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{path_dark}">'
            f'<img src="{path_light}" width="{width}" alt="{alt}"></picture>')


def _date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%b %d").replace(" 0", " ")
    except ValueError:
        return iso[:10]


# ------------------------------------------------------------------ challenges
def report_card(ch: dict, data: dict) -> str:
    names = {b["id"]: b["name"] for b in data["bugs"]}
    buttons = " ".join(f'<kbd><a href="{answer_url("report", ch["id"], opt)}">{names[opt]}</a></kbd>'
                       for opt in ch["options"])
    return ('<b>🕵️ Bug report</b> <sub>· easier</sub><br><br>'
            f'<i>“{html.escape(ch["text"])}”</i><br><br>'
            f'<b>Which bug did this?</b><br><br>{buttons}')


def code_card(ch: dict) -> str:
    width = len(str(len(ch["lines"])))
    body = "\n".join(f"{i:>{width}}  {html.escape(line)}" for i, line in enumerate(ch["lines"], 1))
    buttons = " ".join(f'<kbd><a href="{answer_url("code", ch["id"], str(i))}">Line {i}</a></kbd>'
                       for i in range(1, len(ch["lines"]) + 1))
    lang = "Python" if ch["lang"] == "python" else "JavaScript"
    return ('<b>🔍 Code challenge</b> <sub>· double points</sub><br>'
            f'<pre>{body}</pre>'
            f'<b>Which line has the bug?</b> <sub>{lang}</sub><br><br>{buttons}')


def challenge_table(state: dict, data: dict, challenges: dict) -> str:
    rep = engine.current_challenge(state, challenges, "report")
    code = engine.current_challenge(state, challenges, "code")
    return ('<table><tr>'
            f'<td width="50%" valign="top">{report_card(rep, data)}</td>'
            f'<td width="50%" valign="top">{code_card(code)}</td>'
            '</tr></table>')


# ------------------------------------------------------------------ bugdex + board
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


def section(state: dict, data: dict, challenges: dict) -> str:
    total = len(data["bugs"])
    if state["total"]:
        board = side_tables(state, data)
        footer = (f'<p align="center"><sub>Total catches: <b>{state["total"]}</b> · Bugs discovered: '
                  f'<b>{engine.discovered(state)} / {total}</b></sub></p>')
    else:
        board = '<p align="center"><b>No hunters yet. Be the first to catch one!</b></p>'
        footer = ""
    return "\n".join([
        START,
        challenge_table(state, data, challenges),
        f'<p align="center"><sub>Each answer opens a pre-filled issue. Press <b>Create</b> and a bot replies in about a minute. '
        f'{engine.MAX_TRIES} tries per challenge · new challenges after {engine.SOLVES_TO_ROTATE} solves or every day.</sub></p>',
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
BACK = f"[Back to the profile →]({PROFILE_URL})"


def reply_caught(result: dict, data: dict) -> str:
    bug = result["bug"]
    rarity = data["rarities"][bug["rarity"]]
    h = result["hunter"]
    extras = []
    if result["mode"] == "code":
        extras.append("double points for a code challenge")
    if result["first_solver"]:
        extras.append(f"+{engine.FIRST_SOLVER_BONUS} first-solver bonus")
    lines = [
        f"## 🎯 Correct! You caught **{bug['name']}**",
        "",
        f'<img src="{RAW_BASE}/game/art/{bug["id"]}-light.svg" width="160" alt="{bug["name"]}">',
        "",
        f"{rarity['emoji']} **{rarity['label']}** · **+{result['points']} pts**" + (f" ({', '.join(extras)})" if extras else ""),
        "",
        f"**Why:** {result['challenge']['explain']}",
        "",
        f"> {bug['flavor']}",
        "",
    ]
    if result.get("first_ever"):
        lines += ["✨ **First ever catch of this bug!** It's now unlocked in the Bugdex.", ""]
    lines += [f"Your totals: **{h['catches']}** caught · **{h['points']}** pts.", "", BACK]
    return "\n".join(lines)


def reply_wrong(result: dict) -> str:
    left = result["tries_left"]
    return (f"## 🐛 The bug escaped\n\nNot this one. **Hint:** {result['challenge']['hint']}\n\n"
            f"You have **{left}** {'try' if left == 1 else 'tries'} left on this challenge.\n\n{BACK}")


def reply_out_of_tries(result: dict) -> str:
    return ("## 🫥 That one got away\n\nYou've used all your tries on this challenge. "
            f"A fresh one appears after {engine.SOLVES_TO_ROTATE} people solve it, or tomorrow.\n\n{BACK}")


def reply_already_solved() -> str:
    return f"You already caught this one. 👍 Try the other challenge, or come back when a new one appears.\n\n{BACK}"


def reply_stale() -> str:
    return f"⏳ That challenge has already rotated. There's a fresh one waiting on the profile.\n\n{BACK}"


def reply_invalid_option() -> str:
    return f"🤔 That answer isn't one of the options. Use the buttons on the profile so the title stays exact.\n\n{BACK}"


def reply_limit(result: dict) -> str:
    return f"😴 You've hit today's limit of {result['limit']} answers (UTC). Come back tomorrow!\n\n{BACK}"


def reply_unknown() -> str:
    return ("🤔 I couldn't read that. Answers come from the buttons on the profile, "
            f"with titles like `bughunt: code c05 3`.\n\n{BACK}")


def reply_duplicate() -> str:
    return f"This answer was already counted. 👍\n\n{BACK}"


def reply_for(result: dict, data: dict) -> str:
    status = result["status"]
    if status == "caught":
        return reply_caught(result, data)
    if status == "wrong":
        return reply_wrong(result)
    if status == "out_of_tries":
        return reply_out_of_tries(result)
    if status == "already_solved":
        return reply_already_solved()
    if status == "stale":
        return reply_stale()
    if status == "invalid_option":
        return reply_invalid_option()
    if status == "limit":
        return reply_limit(result)
    return reply_duplicate()
