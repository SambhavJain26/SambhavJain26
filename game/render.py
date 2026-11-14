"""Bug Hunt: turn game state into README markdown and issue replies (pure functions)."""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from . import engine

OWNER = "SambhavJain26"
REPO = "SambhavJain26"
BRANCH = "main"
PROFILE_URL = f"https://github.com/{OWNER}"
GAME_URL = f"{PROFILE_URL}#bug-hunt"
RAW_BASE = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}"

START = "<!-- BUGHUNT:START -->"
END = "<!-- BUGHUNT:END -->"

ISSUE_BODY = ("Just press **Create** without changing the title. "
              "In about a minute a bug will appear here with a challenge. Answer it in a comment to catch it. 🐛")
CATCH_URL = (f"https://github.com/{OWNER}/{REPO}/issues/new"
             f"?title={quote('bughunt: catch')}&body={quote(ISSUE_BODY)}")
LANG = {"python": "python", "javascript": "javascript"}


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
        footer = (f'<p align="center"><sub>Total catches: <b>{state["total"]}</b> · Bugs discovered: '
                  f'<b>{engine.discovered(state)} / {total}</b></sub></p>')
    else:
        board = '<p align="center"><b>No hunters yet. Be the first to catch one!</b></p>'
        footer = ""
    return "\n".join([
        START,
        f'<p align="center"><a href="{CATCH_URL}">{button}</a></p>',
        '<p align="center"><sub>🎲 Luck decides which bug shows up · 🧠 skill decides if you catch it<br>'
        'Press <b>Create</b> on the issue, then answer the bot\'s challenge in a comment.</sub></p>',
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
BACK = f"[Back to the profile →]({GAME_URL})"


def _example_letter(ch: dict, options: list[str]) -> str:
    """An example that is never the right answer, so the hint can't give it away."""
    return next(engine.LETTERS[i] for i, opt in enumerate(options) if opt != ch["bug"])


def _example_line(ch: dict) -> int:
    return next(i for i in range(1, len(ch["lines"]) + 1) if i not in ch["answer"])


def _challenge_block(mode: str, ch: dict, data: dict, options: list[str] | None = None) -> list[str]:
    names = {b["id"]: b["name"] for b in data["bugs"]}
    if mode == "report":
        return [
            "### 🕵️ Bug report",
            "",
            f"> {ch['text']}",
            "",
            "**Which bug did this?**",
            "",
            *[f"**{engine.LETTERS[i]}.** {names[opt]}  " for i, opt in enumerate(options)],
            "",
            f"👉 **Reply with just the letter**, for example `{_example_letter(ch, options)}`.",
        ]
    width = len(str(len(ch["lines"])))
    code = "\n".join(f"{i:>{width}}  {line}" for i, line in enumerate(ch["lines"], 1))
    return [
        "### 🔍 Code challenge · double points",
        "",
        f"```{LANG[ch['lang']]}",
        code,
        "```",
        "",
        "**Which line has the bug?**",
        "",
        f"👉 **Reply with just the line number**, for example `{_example_line(ch)}`.",
    ]


def reply_encounter(result: dict, data: dict) -> str:
    bug = result["bug"]
    rarity = data["rarities"][bug["rarity"]]
    return "\n".join([
        f"## 🎲 A wild **{rarity['label']}** bug appeared! {rarity['emoji']}",
        "",
        f'<img src="{RAW_BASE}/game/art/unknown-{bug["rarity"]}-light.svg" width="120" alt="An undiscovered {rarity["label"]} bug">',
        "",
        "It's hiding somewhere in here. Find it to catch it.",
        "",
        *_challenge_block(result["mode"], result["challenge"], data, result.get("options")),
        "",
        f"<sub>{engine.MAX_TRIES} tries · the bug crawls away if nobody answers within a day</sub>",
    ])


def reply_caught(result: dict, data: dict) -> str:
    bug = result["bug"]
    rarity = data["rarities"][bug["rarity"]]
    h = result["hunter"]
    extras = []
    if result["mode"] == "code":
        extras.append("double points for code")
    if result["first_ever"]:
        extras.append(f"+{engine.DISCOVERER_BONUS} discoverer bonus")
    lines = [
        f"## 🎯 Caught it! It was **{bug['name']}**",
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
    if result["first_ever"]:
        lines += ["✨ **You're the first person ever to catch this bug!** It's now unlocked in the Bugdex.", ""]
    lines += [f"Your totals: **{h['catches']}** caught · **{h['points']}** pts.", "",
              f"{BACK} · [Catch another]({CATCH_URL})"]
    return "\n".join(lines)


def reply_wrong(result: dict) -> str:
    left = result["tries_left"]
    return (f"🐛 **Not there.** Hint: {result['challenge']['hint']}\n\n"
            f"**{left}** {'try' if left == 1 else 'tries'} left. Reply with another answer.")


def reply_escaped(result: dict) -> str:
    return (f"## 💨 The bug escaped\n\nIt slipped away after {engine.MAX_TRIES} tries. "
            f"There are plenty more where it came from.\n\n{BACK} · [Catch another]({CATCH_URL})")


def reply_invalid(result: dict) -> str:
    if result["encounter"]["mode"] == "report":
        return "🤔 Reply with just one letter: `A`, `B`, `C` or `D`."
    n = len(result["challenge"]["lines"])
    return f"🤔 Reply with just a line number from `1` to `{n}`."


def reply_expired() -> str:
    return f"🐾 The bug crawled away while nobody was looking. Come back and try again!\n\n{BACK}"


def reply_limit(result: dict) -> str:
    return f"😴 You've hunted {result['limit']} bugs today (UTC). Come back tomorrow!\n\n{BACK}"


def reply_unknown() -> str:
    return (f"🤔 I couldn't read that title. Start a hunt with the **Catch a bug** button on the profile, "
            f"which opens an issue titled exactly `bughunt: catch`.\n\n{BACK}")


def reply_for_answer(result: dict, data: dict) -> str:
    status = result["status"]
    if status == "caught":
        return reply_caught(result, data)
    if status == "wrong":
        return reply_wrong(result)
    if status == "escaped":
        return reply_escaped(result)
    return reply_invalid(result)
