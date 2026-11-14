"""Copy the game's data, art and fonts into docs/, which GitHub Pages serves.

Run from the repo root after changing bugs, challenges or art:
  python tools/build_site.py

docs/index.html and docs/game.js are hand-written; everything this script
copies is generated, so game/ stays the single source of truth.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def main() -> None:
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    for name in ("bugs.json", "challenges.json"):
        shutil.copyfile(ROOT / "game" / name, DOCS / "data" / name)
    art = DOCS / "art"
    if art.exists():
        shutil.rmtree(art)
    shutil.copytree(ROOT / "game" / "art", art)
    fonts = DOCS / "fonts"
    fonts.mkdir(exist_ok=True)
    for name in ("InstrumentSerif-Regular.ttf", "InstrumentSerif-Italic.ttf", "OFL.txt"):
        shutil.copyfile(ROOT / "tools" / "fonts" / name, fonts / name)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print("site data copied into docs/")


if __name__ == "__main__":
    main()
