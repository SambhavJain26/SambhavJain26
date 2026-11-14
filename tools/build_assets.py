"""Build the static SVG assets for the profile README.

Run from the repo root:  python tools/build_assets.py

Generates (light + dark for each):
  assets/header-*.svg         animated header in the jainsambhav.com style
  assets/cards/*-*.svg        selected-work cards
  assets/catch-button-*.svg   Bug Hunt call-to-action
  game/art/<bug>-*.svg        Bugdex tiles (+ "?" silhouettes for undiscovered bugs)

Fonts: Instrument Serif (SIL Open Font License, see tools/fonts/OFL.txt) is
subset to the characters each file uses and embedded as a data URI, because
SVGs shown through <img> cannot load web fonts.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "tools" / "fonts"

# Design tokens copied from jainsambhav.com (light / dark themes).
THEMES = {
    "light": {
        "paper": "#fafaf9", "ink": "#191a1c", "muted": "#62636a", "rule": "#dededb",
        "soft": "#f0f0ed", "card": "#ffffff", "red": "#e6243f", "blue": "#145cff",
        "dot": "#c6cad1", "limb": "#2b2d31", "shadow": "0.08", "sil": "#d9dad6",
        "btn_bg": "#191a1c", "btn_fg": "#fafaf9",
    },
    "dark": {
        "paper": "#14161b", "ink": "#f2f2f0", "muted": "#b5b9c3", "rule": "#373b45",
        "soft": "#22262f", "card": "#191c23", "red": "#ed4056", "blue": "#497dff",
        "dot": "#4a505d", "limb": "#cfd3da", "shadow": "0.30", "sil": "#2c303a",
        "btn_bg": "#f2f2f0", "btn_fg": "#14161b",
    },
}

SANS = "'IBM Plex Sans','Segoe UI',Helvetica,Arial,sans-serif"
DISPLAY_SANS = "'Poppins','Segoe UI',Helvetica,Arial,sans-serif"
MONO = "'IBM Plex Mono',Consolas,'SFMono-Regular',Menlo,monospace"


# --------------------------------------------------------------------------- fonts
def _font_face(family: str, ttf: str, text: str, italic: bool = False) -> str:
    """Return an @font-face rule embedding only the glyphs needed for `text`."""
    font = TTFont(FONTS / ttf)
    opts = subset.Options()
    opts.layout_features = ["kern", "liga"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(text=text + " ")
    sub.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    style = "italic" if italic else "normal"
    return (f"@font-face{{font-family:'{family}';font-style:{style};font-weight:400;"
            f"src:url(data:font/ttf;base64,{b64}) format('truetype');}}")


def serif_faces(regular_text: str = "", italic_text: str = "") -> str:
    faces = []
    if regular_text:
        faces.append(_font_face("ISerif", "InstrumentSerif-Regular.ttf", regular_text))
    if italic_text:
        faces.append(_font_face("ISerifItalic", "InstrumentSerif-Italic.ttf", italic_text, italic=True))
    return "".join(faces)


SERIF = "'ISerif','Instrument Serif',Georgia,'Times New Roman',serif"
SERIF_IT = "'ISerifItalic','Instrument Serif',Georgia,'Times New Roman',serif"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write(path: Path, svg: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8", newline="\n")


REDUCED_MOTION = "@media (prefers-reduced-motion: reduce){*{animation:none!important}.in{opacity:1!important}}"


# --------------------------------------------------------------------------- header
def header(theme: str) -> str:
    t = THEMES[theme]
    W, H = 1200, 380
    name_regular, name_italic = "Sambhav ", "Jain."
    faces = serif_faces(regular_text=name_regular + "sj.", italic_text=name_italic)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Sambhav Jain. AI and software engineering. Automation and operations.">
<title>Sambhav Jain: AI &amp; Software Engineering · Automation &amp; Operations</title>
<defs>
<style>
{faces}
.label{{font:600 13px {SANS};letter-spacing:3.4px;fill:{t['muted']}}}
.name{{font-family:{SERIF};font-size:124px;fill:{t['ink']}}}
.it{{font-family:{SERIF_IT};font-style:italic}}
.mono{{font-family:{SERIF};font-size:40px;fill:{t['ink']}}}
.pill{{font:500 14px {SANS};fill:{t['ink']}}}
.pt{{font:500 23px {DISPLAY_SANS};fill:{t['ink']}}}
.ps{{font:400 16px {SANS};fill:{t['muted']}}}
.in{{animation:rise 1s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box}}
.d1{{animation-delay:.05s}}.d2{{animation-delay:.3s}}.d3{{animation-delay:.85s}}.d4{{animation-delay:1.1s}}.d5{{animation-delay:1.4s}}
@keyframes rise{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:translateY(0)}}}}
.pulse{{transform-box:fill-box;transform-origin:center;animation:pulse 3s ease-in-out infinite}}
.pulse.b{{animation-delay:1.5s}}
@keyframes pulse{{0%,100%{{transform:scale(1);opacity:1}}50%{{transform:scale(1.55);opacity:.55}}}}
.ring{{transform-box:fill-box;transform-origin:center;animation:ring 2.4s ease-out infinite}}
@keyframes ring{{0%{{transform:scale(.6);opacity:.7}}100%{{transform:scale(2.4);opacity:0}}}}
{REDUCED_MOTION}
</style>
<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="11" cy="11" r="1.15" fill="{t['dot']}"/></pattern>
<radialGradient id="veil" cx="50%" cy="52%" r="62%"><stop offset="0" stop-color="{t['paper']}" stop-opacity="1"/><stop offset=".55" stop-color="{t['paper']}" stop-opacity=".82"/><stop offset="1" stop-color="{t['paper']}" stop-opacity="0"/></radialGradient>
<clipPath id="frame"><rect width="{W}" height="{H}" rx="22"/></clipPath>
</defs>
<g clip-path="url(#frame)">
<rect width="{W}" height="{H}" fill="{t['paper']}"/>
<rect width="{W}" height="{H}" fill="url(#dots)"/>
<rect width="{W}" height="{H}" fill="url(#veil)"/>
</g>
<rect x=".75" y=".75" width="{W-1.5}" height="{H-1.5}" rx="21.5" fill="none" stroke="{t['rule']}" stroke-width="1.5"/>

<text class="mono in d1" x="56" y="74">sj<tspan fill="{t['red']}">.</tspan></text>

<g class="in d1">
<rect x="880" y="42" width="264" height="40" rx="20" fill="{t['card']}" stroke="{t['rule']}"/>
<circle class="ring" cx="904" cy="62" r="5" fill="none" stroke="{t['blue']}" stroke-width="2"/>
<circle cx="904" cy="62" r="5" fill="{t['blue']}"/>
<text class="pill" x="920" y="67">Open to remote roles · IST</text>
</g>

<text class="label in d1" x="{W/2}" y="128" text-anchor="middle">A LITTLE CURIOSITY. A LOT OF BUILDING.</text>
<text class="name in d2" x="{W/2}" y="246" text-anchor="middle">{name_regular}<tspan class="it">{name_italic}</tspan></text>

<g class="in d3">
<circle class="pulse" cx="64" cy="301" r="5" fill="{t['red']}"/>
<text class="pt" x="80" y="309">AI &amp; Software Engineering</text>
<text class="ps" x="64" y="338">Backend services, AI systems and developer tools.</text>
</g>
<g class="in d4">
<circle class="pulse b" cx="1136" cy="301" r="5" fill="{t['blue']}"/>
<text class="pt" x="1120" y="309" text-anchor="end">Automation &amp; Operations</text>
<text class="ps" x="1136" y="338" text-anchor="end">Connecting tools and automating everyday workflows.</text>
</g>
</svg>
"""


# --------------------------------------------------------------------------- cards
CARDS = [
    {
        "slug": "cold-email",
        "tag": "TYPESCRIPT · REAL USE", "accent": "red",
        "title": ["Event-Sourced Cold Email", "& Deliverability Engine"],
        "result": "~3,500 emails sent to ~800 leads",
        "detail": "Event-sourced lead status · mailbox caps · IMAP reply sorting",
        "stack": "Fastify · PostgreSQL · pg-boss · React",
    },
    {
        "slug": "visa-alerts",
        "tag": "PYTHON · REAL USE", "accent": "red",
        "title": ["H-1B Visa Appointment", "Alert Engine"],
        "result": "Helped a family member book an H-1B appointment",
        "detail": "24/7 read-only watcher · Telegram alerts · 160 tests in CI",
        "stack": "Telethon · Playwright · OpenAI · SQLite · Docker",
    },
    {
        "slug": "leasing",
        "tag": "N8N DEMO · VIDEO", "accent": "blue",
        "title": ["Inbound Lead Qualification", "& Calendar Booking Pipeline"],
        "result": "Inquiry → tour → income check → lease signing",
        "detail": "Cal.com · Plaid sandbox · DocuSign · manager approval",
        "stack": "n8n · PostgreSQL · JavaScript",
    },
    {
        "slug": "turnover",
        "tag": "N8N DEMO · VIDEO", "accent": "blue",
        "title": ["Multi-Stage Operations", "& Task Handoff Engine"],
        "result": "11-stage apartment-turnover flow",
        "detail": "Stall watchdog · error workflow · Telegram approvals",
        "stack": "n8n · PostgreSQL · OpenAI · Docker",
    },
]


def card(c: dict, theme: str) -> str:
    t = THEMES[theme]
    W, H = 560, 260
    accent = t[c["accent"]]
    faces = serif_faces(regular_text="".join(c["title"]))
    title = "".join(
        f'<text class="title" x="32" y="{96 + i * 38}">{esc(line)}</text>' for i, line in enumerate(c["title"])
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(' '.join(c['title']))}: {esc(c['result'])}">
<defs><style>
{faces}
.tag{{font:600 11.5px {SANS};letter-spacing:2.2px;fill:{t['muted']}}}
.title{{font-family:{SERIF};font-size:34px;fill:{t['ink']}}}
.res{{font:600 16.5px {SANS};fill:{t['ink']}}}
.det{{font:400 14px {SANS};fill:{t['muted']}}}
.stk{{font:400 12.5px {MONO};fill:{t['muted']}}}
.arrow{{transform-box:fill-box;transform-origin:center;animation:nudge 3.2s ease-in-out infinite}}
@keyframes nudge{{0%,70%,100%{{transform:translate(0,0)}}80%{{transform:translate(2px,-2px)}}}}
{REDUCED_MOTION}
</style></defs>
<rect x=".75" y=".75" width="{W-1.5}" height="{H-1.5}" rx="18" fill="{t['card']}" stroke="{t['rule']}" stroke-width="1.5"/>
<circle cx="38" cy="42" r="4.5" fill="{accent}"/>
<text class="tag" x="52" y="46">{esc(c['tag'])}</text>
<g class="arrow"><circle cx="520" cy="42" r="17" fill="none" stroke="{t['rule']}" stroke-width="1.5"/>
<path d="M513 49 L527 35 M517 35 H527 V45" fill="none" stroke="{t['ink']}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></g>
{title}
<rect x="32" y="158" width="3" height="22" rx="1.5" fill="{accent}"/>
<text class="res" x="44" y="175">{esc(c['result'])}</text>
<text class="det" x="32" y="207">{esc(c['detail'])}</text>
<text class="stk" x="32" y="234">{esc(c['stack'])}</text>
</svg>
"""


# --------------------------------------------------------------------------- "More work" link
def more_work(theme: str) -> str:
    t = THEMES[theme]
    W, H = 168, 40
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="More work">
<defs><style>
.l{{font:500 15px {SANS};fill:{t['ink']}}}
.arrow{{animation:nudge 2.6s ease-in-out infinite}}
@keyframes nudge{{0%,70%,100%{{transform:translate(0,0)}}80%{{transform:translate(2px,-2px)}}}}
{REDUCED_MOTION}
</style></defs>
<rect x=".75" y=".75" width="{W-1.5}" height="{H-1.5}" rx="{(H-1.5)/2}" fill="{t['card']}" stroke="{t['rule']}" stroke-width="1.5"/>
<circle cx="22" cy="20" r="4" fill="{t['red']}"/>
<text class="l" x="34" y="25">More work</text>
<g class="arrow"><circle cx="142" cy="20" r="12" fill="{t['ink']}"/>
<path d="M137 25 L147 15 M140 15 H147 V22" fill="none" stroke="{t['card']}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></g>
</svg>
"""


# --------------------------------------------------------------------------- button
def catch_button(theme: str) -> str:
    t = THEMES[theme]
    W, H = 440, 76
    label = "Catch a bug"
    faces = serif_faces(regular_text=label)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Catch a bug">
<defs><style>
{faces}
.l{{font-family:{SERIF};font-size:32px;fill:{t['btn_fg']}}}
.s{{font:500 12px {SANS};letter-spacing:2px;fill:{t['btn_fg']};opacity:.7}}
.net{{transform-box:fill-box;transform-origin:20% 90%;animation:swing 2.6s ease-in-out infinite}}
@keyframes swing{{0%,100%{{transform:rotate(-10deg)}}50%{{transform:rotate(12deg)}}}}
.bug{{animation:hop 2.6s ease-in-out infinite}}
@keyframes hop{{0%,100%{{transform:translate(0,0)}}50%{{transform:translate(-6px,-3px)}}}}
{REDUCED_MOTION}
</style></defs>
<rect width="{W}" height="{H}" rx="{H/2}" fill="{t['btn_bg']}"/>
<g class="net" stroke="{t['btn_fg']}" stroke-width="2.4" fill="none" stroke-linecap="round">
<line x1="40" y1="56" x2="56" y2="38"/>
<ellipse cx="64" cy="29" rx="13" ry="10" transform="rotate(-40 64 29)"/>
<path d="M56 23 L72 35 M60 19 L75 31 M54 29 L66 39" stroke-width="1.2" opacity=".7"/>
</g>
<g class="bug"><ellipse cx="96" cy="44" rx="6" ry="7.5" fill="{t['red']}"/><circle cx="96" cy="35" r="3.6" fill="{t['red']}"/></g>
<text class="l" x="124" y="47">{label}</text>
<text class="s" x="300" y="44">PLAY  →</text>
</svg>
"""


# --------------------------------------------------------------------------- bugs
def _shade(hex_color: str, factor: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, min(255, int(c * factor))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _legs(color: str, left: int = 3, right: int = 3, opacity: float = 1.0, dash: str = "") -> str:
    out = []
    for side, n in ((-1, left), (1, right)):
        ys = [96 + i * (44 / max(1, n - 1)) for i in range(n)] if n > 1 else [118]
        for y in ys:
            x0 = 100 + side * 34
            out.append(
                f'<path d="M{x0} {y:.1f} Q{x0 + side * 22} {y - 8:.1f} {x0 + side * 36} {y + 8:.1f}" '
                f'fill="none" stroke="{color}" stroke-width="4.5" stroke-linecap="round" opacity="{opacity}"{dash}/>'
            )
    return "".join(out)


def _antennae(color: str, opacity: float = 1.0) -> str:
    return (
        f'<g opacity="{opacity}"><path d="M92 40 Q84 18 70 16 M108 40 Q116 18 130 16" fill="none" stroke="{color}" '
        f'stroke-width="3.5" stroke-linecap="round"/><circle cx="70" cy="16" r="4.5" fill="{color}"/>'
        f'<circle cx="130" cy="16" r="4.5" fill="{color}"/></g>'
    )


def _eyes(ink: str, question: bool = False) -> str:
    if question:
        return ('<circle cx="92" cy="52" r="7" fill="#fff"/><circle cx="108" cy="52" r="7" fill="#fff"/>'
                f'<text x="92" y="57" text-anchor="middle" style="font:700 11px {SANS}" fill="#191a1c">?</text>'
                f'<text x="108" y="57" text-anchor="middle" style="font:700 11px {SANS}" fill="#191a1c">?</text>')
    return ('<circle cx="92" cy="52" r="7" fill="#fff"/><circle cx="108" cy="52" r="7" fill="#fff"/>'
            '<circle cx="93.5" cy="53" r="3.3" fill="#191a1c"/><circle cx="109.5" cy="53" r="3.3" fill="#191a1c"/>')


def _body(fill: str, extra_cls: str = "") -> str:
    cls = f' class="{extra_cls}"' if extra_cls else ""
    return (f'<ellipse{cls} cx="100" cy="114" rx="40" ry="48" fill="{fill}"/>'
            f'<ellipse cx="86" cy="94" rx="9" ry="15" fill="#fff" opacity=".22"/>'
            f'<line x1="100" y1="72" x2="100" y2="160" stroke="#000" stroke-opacity=".18" stroke-width="2.5"/>')


def _head(fill: str) -> str:
    return f'<circle cx="100" cy="54" r="22" fill="{fill}"/>'


def bug_tile(bug: dict, rarity: dict, theme: str, silhouette: bool = False) -> str:
    t = THEMES[theme]
    body, head = bug["body"], _shade(bug["body"], 0.72)
    limb = t["limb"]
    styles: list[str] = []
    serif_text = ""
    under, over = "", ""
    legs_l, legs_r = 3, 3
    eyes_q = False
    body_cls = ""
    group_cls = ""
    group_tf = ""
    bid = bug["id"]

    if silhouette:
        serif_text = "?"
        frame = (f'<rect x="3" y="3" width="194" height="194" rx="24" fill="{t["card"]}" stroke="{t["rule"]}" '
                 f'stroke-width="2.5" stroke-dasharray="7 7"/>')
        s = t["sil"]
        art = (_legs(s) + _antennae(s) + f'<ellipse cx="100" cy="114" rx="40" ry="48" fill="{s}"/>' + _head(s)
               + f'<text x="100" y="134" text-anchor="middle" style="font-family:{SERIF};font-size:58px" fill="{t["card"]}">?</text>')
        faces = serif_faces(regular_text=serif_text)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200" role="img" '
                f'aria-label="Undiscovered bug"><defs><style>{faces}</style></defs>{frame}'
                f'<ellipse cx="100" cy="172" rx="44" ry="7" fill="#000" opacity="{t["shadow"]}"/>{art}</svg>\n')

    if bid == "typo":
        serif_text = "teh"
        over = f'<text x="100" y="126" text-anchor="middle" style="font-family:{SERIF};font-size:28px" fill="#fff">teh</text>'
    elif bid == "missing-semicolon":
        over = ('<circle cx="100" cy="104" r="6" fill="#fff"/><circle cx="100" cy="126" r="6" fill="#fff"/>'
                '<path d="M100 132 q2 10 -6 16" fill="none" stroke="#fff" stroke-width="3" stroke-dasharray="3 3" '
                'stroke-linecap="round" opacity=".85"/>')
    elif bid == "trailing-whitespace":
        under = (f'<g fill="{t["muted"]}"><circle cx="150" cy="160" r="3.5" opacity=".8"/>'
                 '<circle cx="164" cy="166" r="3" opacity=".55"/><circle cx="177" cy="171" r="2.5" opacity=".3"/></g>')
        over = '<path d="M86 118 v8 h28 v-8" fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>'
    elif bid == "unclosed-bracket":
        serif_text = "{"
        over = f'<text x="100" y="140" text-anchor="middle" style="font-family:{SERIF};font-size:62px" fill="#fff">{{</text>'
    elif bid == "off-by-one":
        legs_l, legs_r = 4, 3
        over = f'<text x="100" y="124" text-anchor="middle" style="font:700 19px {SANS}" fill="#fff">n+1</text>'
    elif bid == "flaky-test":
        body_cls = "flaky"
        styles.append("@keyframes flk{0%,49%{fill:#2e9e5b}50%,100%{fill:#e6243f}}"
                      ".flaky{animation:flk 2.4s steps(1) infinite}"
                      "@keyframes onA{0%,49%{opacity:1}50%,100%{opacity:0}}@keyframes onB{0%,49%{opacity:0}50%,100%{opacity:1}}"
                      ".pa{animation:onA 2.4s steps(1) infinite}.pb{animation:onB 2.4s steps(1) infinite;opacity:0}")
        over = ('<path class="pa" d="M86 116 l9 9 l18 -20" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
                '<path class="pb" d="M88 104 l24 24 M112 104 l-24 24" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round"/>')
    elif bid == "merge-conflict":
        styles.append("")
        body = "url(#halves)"
        head = _shade("#145cff", 0.7)
        under = ('<defs><linearGradient id="halves" x1="0" x2="1" y1="0" y2="0">'
                 '<stop offset=".5" stop-color="#145cff"/><stop offset=".5" stop-color="#e6243f"/></linearGradient></defs>')
        over = (f'<text x="100" y="100" text-anchor="middle" style="font:700 12px {MONO}" fill="#fff">&lt;&lt;&lt;&lt;</text>'
                f'<text x="100" y="118" text-anchor="middle" style="font:700 12px {MONO}" fill="#fff">====</text>'
                f'<text x="100" y="136" text-anchor="middle" style="font:700 12px {MONO}" fill="#fff">&gt;&gt;&gt;&gt;</text>')
    elif bid == "null-pointer":
        frame_fill = t["card"]
        art = (_legs(limb, opacity=.45, dash=' stroke-dasharray="6 6"') + _antennae(limb, opacity=.45)
               + f'<ellipse cx="100" cy="114" rx="40" ry="48" fill="{frame_fill}" stroke="{t["ink"]}" stroke-width="3" stroke-dasharray="7 6"/>'
               + f'<circle cx="100" cy="54" r="22" fill="{frame_fill}" stroke="{t["ink"]}" stroke-width="3" stroke-dasharray="6 5"/>'
               + _eyes(t["ink"])
               + f'<circle cx="100" cy="116" r="16" fill="none" stroke="{t["ink"]}" stroke-width="3.5"/>'
               + f'<line x1="86" y1="134" x2="114" y2="98" stroke="{t["ink"]}" stroke-width="3.5" stroke-linecap="round"/>')
        return _tile_wrap(bug, rarity, theme, art, styles, serif_text)
    elif bid == "memory-leak":
        styles.append("@keyframes drip{0%{transform:translateY(0);opacity:0}15%{opacity:1}100%{transform:translateY(22px);opacity:0}}"
                      ".drop{animation:drip 1.8s ease-in infinite}.drop.b{animation-delay:.9s}")
        under = f'<ellipse cx="100" cy="184" rx="24" ry="4" fill="{bug["body"]}" opacity=".45"/>'
        over = ('<g fill="#fff" opacity=".9"><rect x="84" y="118" width="7" height="14" rx="2"/>'
                '<rect x="96.5" y="110" width="7" height="22" rx="2"/><rect x="109" y="100" width="7" height="32" rx="2"/></g>'
                f'<path class="drop" d="M100 160 q-6 9 0 13 q6 -4 0 -13z" fill="{bug["body"]}"/>'
                f'<path class="drop b" d="M92 158 q-5 8 0 11 q5 -3 0 -11z" fill="{bug["body"]}"/>')
    elif bid == "race-condition":
        group_tf = ' transform="rotate(-10 100 110)"'
        styles.append("@keyframes zoom{from{stroke-dashoffset:0}to{stroke-dashoffset:-40}}"
                      ".speed{stroke-dasharray:14 6;animation:zoom .6s linear infinite}")
        under = (f'<g stroke="{t["muted"]}" stroke-width="3.5" stroke-linecap="round" class="speed">'
                 '<line x1="14" y1="96" x2="52" y2="96"/><line x1="8" y1="116" x2="50" y2="116"/><line x1="16" y1="136" x2="52" y2="136"/></g>'
                 f'<g transform="translate(150 22)"><line x1="0" y1="0" x2="0" y2="34" stroke="{limb}" stroke-width="2.5"/>'
                 f'<rect x="0" y="0" width="22" height="15" fill="#fff" stroke="{limb}" stroke-width="1"/>'
                 f'<rect x="0" y="0" width="5.5" height="5" fill="{limb}"/><rect x="11" y="0" width="5.5" height="5" fill="{limb}"/>'
                 f'<rect x="5.5" y="5" width="5.5" height="5" fill="{limb}"/><rect x="16.5" y="5" width="5.5" height="5" fill="{limb}"/>'
                 f'<rect x="0" y="10" width="5.5" height="5" fill="{limb}"/><rect x="11" y="10" width="5.5" height="5" fill="{limb}"/></g>')
        over = '<text x="100" y="124" text-anchor="middle" style="font:800 20px ' + SANS + '" fill="#fff">2×</text>'
    elif bid == "heisenbug":
        group_cls = "ghost"
        eyes_q = True
        styles.append("@keyframes ghost{0%,30%{opacity:1}36%{opacity:.12}40%{opacity:.9}62%{opacity:.9}70%{opacity:.25}78%,100%{opacity:1}}"
                      ".ghost{animation:ghost 3.4s ease-in-out infinite}")
        under = (f'<g fill="none" stroke="{t["muted"]}" stroke-width="3" opacity=".7"><circle cx="160" cy="158" r="13"/>'
                 '<line x1="169" y1="168" x2="182" y2="181" stroke-linecap="round"/></g>')
    elif bid == "timezone-bug":
        styles.append("@keyframes spin{to{transform:rotate(360deg)}}"
                      ".hand{transform-box:view-box;transform-origin:100px 116px;animation:spin 4s linear infinite}"
                      ".hand.h{animation-duration:24s}")
        over = ('<circle cx="100" cy="116" r="23" fill="#fff"/>'
                '<g stroke="#191a1c" stroke-width="2" stroke-linecap="round">'
                '<line x1="100" y1="97" x2="100" y2="101"/><line x1="100" y1="131" x2="100" y2="135"/>'
                '<line x1="81" y1="116" x2="85" y2="116"/><line x1="115" y1="116" x2="119" y2="116"/></g>'
                '<line class="hand h" x1="100" y1="116" x2="100" y2="104" stroke="#191a1c" stroke-width="3.5" stroke-linecap="round"/>'
                '<line class="hand" x1="100" y1="116" x2="111" y2="116" stroke="#e6243f" stroke-width="2.5" stroke-linecap="round"/>'
                '<circle cx="100" cy="116" r="2.5" fill="#191a1c"/>'
                f'<text x="100" y="152" text-anchor="middle" style="font:700 10px {SANS}" fill="#fff">+5:30</text>')
    elif bid == "infinite-loop":
        styles.append("@keyframes run{to{stroke-dashoffset:-120}}"
                      ".inf{stroke-dasharray:28 12;animation:run 1.6s linear infinite}")
        over = ('<path d="M100 116 C92 102 74 102 74 116 C74 130 92 130 100 116 C108 102 126 102 126 116 C126 130 108 130 100 116Z" '
                'fill="none" stroke="#fff" stroke-width="5" opacity=".35"/>'
                '<path class="inf" d="M100 116 C92 102 74 102 74 116 C74 130 92 130 100 116 C108 102 126 102 126 116 C126 130 108 130 100 116Z" '
                'fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round"/>')
    elif bid == "regex-monster":
        styles.append("@keyframes blink{0%,92%,100%{transform:scaleY(1)}95%{transform:scaleY(.1)}}"
                      ".eye3{transform-box:fill-box;transform-origin:center;animation:blink 3.5s infinite}")
        over = ('<g class="eye3"><circle cx="100" cy="38" r="7" fill="#fff"/><circle cx="100" cy="39" r="3.3" fill="#191a1c"/></g>'
                '<path d="M86 68 l4 7 l4 -7 l4 7 l4 -7 l4 7 l4 -7" fill="#fff" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/>'
                f'<text x="100" y="124" text-anchor="middle" style="font:700 17px {MONO}" fill="#fff">/.*/</text>')
    elif bid == "deadlock":
        styles.append("@keyframes shake{0%,86%,100%{transform:translateX(0)}89%{transform:translateX(-3px)}92%{transform:translateX(3px)}95%{transform:translateX(-2px)}}"
                      ".lock{animation:shake 3s ease-in-out infinite}")
        under = (f'<g fill="none" stroke="{t["muted"]}" stroke-width="3" opacity=".7">'
                 '<ellipse cx="34" cy="116" rx="9" ry="6"/><ellipse cx="50" cy="116" rx="9" ry="6"/>'
                 '<ellipse cx="150" cy="116" rx="9" ry="6"/><ellipse cx="166" cy="116" rx="9" ry="6"/></g>')
        over = ('<g class="lock"><path d="M90 112 v-9 a10 10 0 0 1 20 0 v9" fill="none" stroke="#fff" stroke-width="4.5" stroke-linecap="round"/>'
                '<rect x="84" y="110" width="32" height="26" rx="5" fill="#fff"/>'
                '<circle cx="100" cy="121" r="3.5" fill="#0f766e"/><rect x="98.5" y="122" width="3" height="8" rx="1.5" fill="#0f766e"/></g>')
    elif bid == "works-on-my-machine":
        styles.append("@keyframes tw{0%,100%{opacity:.15;transform:scale(.6)}50%{opacity:1;transform:scale(1)}}"
                      ".spk{transform-box:fill-box;transform-origin:center;animation:tw 2.2s ease-in-out infinite}"
                      ".spk.b{animation-delay:.7s}.spk.c{animation-delay:1.4s}"
                      "@keyframes sheen{0%{transform:translateX(-90px)}60%,100%{transform:translateX(90px)}}"
                      ".sheen{animation:sheen 3s ease-in-out infinite}")
        star = "M0 -9 L2.2 -2.2 L9 0 L2.2 2.2 L0 9 L-2.2 2.2 L-9 0 L-2.2 -2.2Z"
        under = (f'<defs><clipPath id="bodyclip"><ellipse cx="100" cy="114" rx="40" ry="48"/></clipPath></defs>'
                 f'<g fill="#f2b705"><path class="spk" transform="translate(36 52)" d="{star}"/>'
                 f'<path class="spk b" transform="translate(166 78)" d="{star}"/><path class="spk c" transform="translate(40 150)" d="{star}"/></g>'
                 f'<g transform="translate(138 132)"><rect x="4" y="0" width="38" height="25" rx="3" fill="{limb}"/>'
                 '<rect x="7" y="3" width="32" height="19" rx="1.5" fill="#2e9e5b"/>'
                 '<path d="M15 12.5 l5 5 l9 -10" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
                 f'<path d="M0 27 h46 l-4 5 h-38z" fill="{limb}"/></g>')
        over = ('<g clip-path="url(#bodyclip)"><rect class="sheen" x="70" y="60" width="22" height="110" fill="#fff" opacity=".35" transform="skewX(-18)"/></g>'
                '<path d="M80 38 L84 18 L92 30 L100 14 L108 30 L116 18 L120 38Z" fill="#f2b705" stroke="#b07f00" stroke-width="2" stroke-linejoin="round"/>'
                '<circle cx="100" cy="30" r="3.4" fill="#e6243f"/>')

    art = (under + f'<g class="{group_cls}"{group_tf}>' + _legs(limb, legs_l, legs_r) + _antennae(limb)
           + (_body(body, body_cls)) + _head(head) + _eyes(t["ink"], eyes_q) + over + "</g>")
    return _tile_wrap(bug, rarity, theme, art, styles, serif_text)


STAR = "M0 -9 L2.2 -2.2 L9 0 L2.2 2.2 L0 9 L-2.2 2.2 L-9 0 L-2.2 -2.2Z"
SPARKLE_SPOTS = [(34, 46), (166, 58), (40, 150), (164, 146), (100, 186)]
SPARKLES_BY_RARITY = {"common": 1, "uncommon": 2, "rare": 3, "epic": 4, "legendary": 5}


def mystery_tile(rarity_key: str, rarity: dict, theme: str) -> str:
    """An undiscovered bug: a glowing, floating silhouette tinted by rarity, with a pulsing '?'."""
    t = THEMES[theme]
    c = rarity["color"]
    tint = ".30" if theme == "light" else ".38"
    glow = ".32" if theme == "light" else ".40"
    faces = serif_faces(regular_text="?")
    n = SPARKLES_BY_RARITY[rarity_key]
    sparkles = "".join(
        f'<path class="spk" style="animation-delay:{i * 0.55:.2f}s" transform="translate({x} {y})" d="{STAR}" fill="{c}"/>'
        for i, (x, y) in enumerate(SPARKLE_SPOTS[:n]))
    crown = ('<path d="M82 34 L86 16 L94 27 L100 12 L106 27 L114 16 L118 34Z" fill="none" '
             f'stroke="{c}" stroke-width="2.5" stroke-linejoin="round" opacity=".8"/>') if rarity_key == "legendary" else ""
    body = (
        f'<g fill="none" stroke="{c}" stroke-width="4" stroke-linecap="round" opacity=".55">'
        + "".join(
            f'<path d="M{100 + s * 34} {y} Q{100 + s * 56} {y - 8} {100 + s * 70} {y + 8}"/>'
            for s in (-1, 1) for y in (96, 118, 140))
        + '<path d="M92 40 Q84 18 70 16 M108 40 Q116 18 130 16"/></g>'
        + f'<ellipse cx="100" cy="114" rx="40" ry="48" fill="{c}" fill-opacity="{tint}" stroke="{c}" stroke-opacity=".6" stroke-width="2"/>'
        + f'<circle cx="100" cy="54" r="22" fill="{c}" fill-opacity="{tint}" stroke="{c}" stroke-opacity=".6" stroke-width="2"/>'
        + crown
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200" role="img" aria-label="Undiscovered {rarity['label']} bug">
<defs><style>{faces}
.ants{{stroke-dasharray:12 7;animation:ants 8s linear infinite}}
@keyframes ants{{to{{stroke-dashoffset:-190}}}}
.bob{{animation:bob 3.2s ease-in-out infinite}}
@keyframes bob{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-6px)}}}}
.ring{{transform-box:fill-box;transform-origin:center;animation:ring 2.2s ease-out infinite}}
@keyframes ring{{0%{{transform:scale(1);opacity:.7}}100%{{transform:scale(1.9);opacity:0}}}}
.spk{{transform-box:fill-box;transform-origin:center;animation:tw 2.4s ease-in-out infinite}}
@keyframes tw{{0%,100%{{opacity:.1;transform:scale(.5)}}50%{{opacity:1;transform:scale(1)}}}}
.sheen{{animation:sheen 4.5s ease-in-out infinite}}
@keyframes sheen{{0%,55%{{transform:translateX(-160px)}}100%{{transform:translateX(260px)}}}}
{REDUCED_MOTION}
</style>
<radialGradient id="glow" cx="50%" cy="56%" r="58%"><stop offset="0" stop-color="{c}" stop-opacity="{glow}"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>
<clipPath id="tile"><rect x="3" y="3" width="194" height="194" rx="24"/></clipPath>
</defs>
<rect x="3" y="3" width="194" height="194" rx="24" fill="{t['card']}"/>
<g clip-path="url(#tile)"><rect width="200" height="200" fill="url(#glow)"/>
<rect class="sheen" x="0" y="-20" width="34" height="240" fill="#fff" opacity="{'.35' if theme == 'light' else '.08'}" transform="skewX(-20)"/></g>
<rect class="ants" x="3" y="3" width="194" height="194" rx="24" fill="none" stroke="{c}" stroke-width="3"/>
{sparkles}
<g class="bob">{body}
<circle class="ring" cx="100" cy="116" r="22" fill="none" stroke="{c}" stroke-width="2.5"/>
<circle cx="100" cy="116" r="22" fill="{c}"/>
<text x="100" y="128" text-anchor="middle" style="font-family:{SERIF};font-size:34px" fill="#fff">?</text></g>
</svg>
"""


def _tile_wrap(bug: dict, rarity: dict, theme: str, art: str, styles: list[str], serif_text: str) -> str:
    t = THEMES[theme]
    faces = serif_faces(regular_text=serif_text) if serif_text else ""
    color = rarity["color"]
    gem = (f'<path d="M176 14 L179.5 21.5 L187.5 22.5 L181.5 28 L183 36 L176 32 L169 36 L170.5 28 L164.5 22.5 L172.5 21.5Z" fill="{color}"/>'
           if bug["rarity"] == "legendary" else f'<circle cx="176" cy="25" r="7" fill="{color}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200" role="img" '
            f'aria-label="{esc(bug["name"])} ({rarity["label"]})"><defs><style>{faces}{"".join(styles)}{REDUCED_MOTION}</style></defs>'
            f'<rect x="3" y="3" width="194" height="194" rx="24" fill="{t["card"]}" stroke="{color}" stroke-width="3"/>{gem}'
            f'<ellipse cx="100" cy="172" rx="44" ry="7" fill="#000" opacity="{t["shadow"]}"/>{art}</svg>\n')


# --------------------------------------------------------------------------- main
def main() -> None:
    data = json.loads((ROOT / "game" / "bugs.json").read_text(encoding="utf-8"))
    for theme in THEMES:
        write(ROOT / "assets" / f"header-{theme}.svg", header(theme))
        write(ROOT / "assets" / f"catch-button-{theme}.svg", catch_button(theme))
        write(ROOT / "assets" / f"more-work-{theme}.svg", more_work(theme))
        for c in CARDS:
            write(ROOT / "assets" / "cards" / f"{c['slug']}-{theme}.svg", card(c, theme))
        for bug in data["bugs"]:
            rarity = data["rarities"][bug["rarity"]]
            write(ROOT / "game" / "art" / f"{bug['id']}-{theme}.svg", bug_tile(bug, rarity, theme))
        for key, rarity in data["rarities"].items():
            write(ROOT / "game" / "art" / f"unknown-{key}-{theme}.svg", mystery_tile(key, rarity, theme))
    print("assets built")


if __name__ == "__main__":
    main()
