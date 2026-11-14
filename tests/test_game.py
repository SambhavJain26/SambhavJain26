import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from game import engine, play, render

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "game" / "bugs.json").read_text(encoding="utf-8"))
CH = json.loads((ROOT / "game" / "challenges.json").read_text(encoding="utf-8"))
BUG_IDS = {b["id"] for b in DATA["bugs"]}
NOW = datetime(2026, 11, 14, 10, tzinfo=timezone.utc)
AT = NOW.isoformat()


def fresh():
    return engine.initial_state(DATA["bugs"])


def issue(n, title, login="hunter"):
    return {"number": n, "title": title, "author": {"login": login}, "createdAt": AT}


class ChallengeBank(unittest.TestCase):
    def test_one_report_and_one_code_challenge_per_bug(self):
        for mode in ("report", "code"):
            self.assertEqual(sorted(c["bug"] for c in CH[mode]), sorted(BUG_IDS), mode)

    def test_every_challenge_is_complete(self):
        for c in CH["report"]:
            self.assertTrue(c["text"] and c["hint"] and c["explain"], c["id"])
        for c in CH["code"]:
            self.assertTrue(3 <= len(c["lines"]) <= 9, c["id"])
            self.assertTrue(all(1 <= a <= len(c["lines"]) for a in c["answer"]), c["id"])
            self.assertLess(len(c["answer"]), len(c["lines"]), c["id"])
            self.assertTrue(c["hint"] and c["explain"], c["id"])

    def test_weights_sum_to_100(self):
        self.assertAlmostEqual(sum(b["weight"] for b in DATA["bugs"]), 100)


class Titles(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(engine.parse_title("bughunt: record timezone-bug code"),
                         {"kind": "record", "bug": "timezone-bug", "mode": "code"})
        self.assertEqual(engine.parse_title("BugHunt:Record Typo REPORT")["bug"], "typo")
        self.assertEqual(engine.parse_title("bughunt: catch"), {"kind": "legacy"})
        self.assertEqual(engine.parse_title("bughunt: record typo code; rm -rf /"), {"kind": "unknown"})
        self.assertIsNone(engine.parse_title("Typo in README"))
        self.assertIsNone(engine.parse_title(None))

    def test_logins(self):
        self.assertTrue(engine.valid_login("octocat"))
        for bad in ["", "-ab", "ab-", "github-actions[bot]", "x" * 40, None]:
            self.assertFalse(engine.valid_login(bad))


class Recording(unittest.TestCase):
    def test_record_with_discoverer_bonus_and_code_double(self):
        s = fresh()
        r = engine.record_catch(s, DATA, "ada", AT, 1, "null-pointer", "code")
        self.assertEqual(r["status"], "recorded")
        self.assertEqual(r["points"], 5 * 2 + engine.DISCOVERER_BONUS)
        r = engine.record_catch(s, DATA, "bob", AT, 2, "null-pointer", "report")
        self.assertEqual(r["points"], 5)
        self.assertFalse(r["first_ever"])
        self.assertEqual(s["counts"]["null-pointer"], 2)

    def test_unknown_bug_and_duplicates(self):
        s = fresh()
        self.assertEqual(engine.record_catch(s, DATA, "ada", AT, 1, "dragon", "code")["status"], "unknown_bug")
        self.assertEqual(engine.record_catch(s, DATA, "ada", AT, 1, "typo", "code")["status"], "duplicate")
        self.assertEqual(s["total"], 0)

    def test_daily_limit_resets_next_day(self):
        s = fresh()
        for i in range(engine.DAILY_LIMIT):
            engine.record_catch(s, DATA, "ada", AT, i + 1, "typo", "report")
        self.assertEqual(engine.record_catch(s, DATA, "ada", AT, 99, "typo", "report")["status"], "limit")
        tomorrow = "2026-11-15T01:00:00+00:00"
        self.assertEqual(engine.record_catch(s, DATA, "ada", tomorrow, 100, "typo", "report")["status"], "recorded")

    def test_best_bug_is_the_rarest(self):
        s = fresh()
        engine.record_catch(s, DATA, "ada", AT, 1, "heisenbug", "report")
        engine.record_catch(s, DATA, "ada", AT, 2, "typo", "report")
        self.assertEqual(s["hunters"]["ada"]["best"], "heisenbug")

    def test_leaderboard_order(self):
        s = fresh()
        engine.record_catch(s, DATA, "low", AT, 1, "typo", "report")
        engine.record_catch(s, DATA, "high", AT, 2, "works-on-my-machine", "code")
        self.assertEqual([k for k, _ in engine.leaderboard(s)], ["high", "low"])


class Runner(unittest.TestCase):
    def test_process_records_and_closes_everything_it_touches(self):
        s = fresh()
        issues = [issue(1, "bughunt: record typo report", "ada-l"), issue(2, "Bug in your site"),
                  issue(3, "bughunt: catch"), issue(4, "bughunt: hello"),
                  issue(5, "bughunt: record typo code", "evil[bot]")]
        out = play.process(issues, s, DATA, NOW)
        self.assertEqual([o["issue"] for o in out], [1, 3, 4, 5])
        self.assertIn("You're on the board", out[0]["body"])
        self.assertIn("moved to an instant game", out[1]["body"])
        self.assertEqual(s["total"], 1)
        again = play.process(issues[:1], s, DATA, NOW)
        self.assertEqual(again, [{"issue": 1, "body": None}])


class ReadmeSection(unittest.TestCase):
    def test_empty_and_busy_board(self):
        s = fresh()
        sec = render.section(s, DATA)
        self.assertIn(render.GAME_URL, sec)
        self.assertIn("No hunters on the board yet", sec)
        self.assertEqual(sec.count('alt="Undiscovered bug"'), len(DATA["bugs"]))
        engine.record_catch(s, DATA, "ada-l", AT, 1, "typo", "report")
        sec = render.section(s, DATA)
        self.assertIn("Top hunters", sec)
        self.assertIn("@ada-l", sec)

    def test_readme_markers_anchors_and_top_bar(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for needle in [render.START, render.END, '<a name="bug-hunt"></a>', '<a name="selected-work"></a>',
                       '<a name="tools"></a>', "assets/bar-light.svg", "### Hey there 👋"]:
            self.assertIn(needle, readme)
        self.assertNotIn("img.shields.io", readme)
        self.assertNotIn("hspace", readme)
        with self.assertRaises(ValueError):
            render.replace_section("no markers", "x")

    def test_game_page_exists(self):
        for f in ["index.html", "game.js", "data/bugs.json", "data/challenges.json", ".nojekyll",
                  "fonts/InstrumentSerif-Regular.ttf", "art/unknown-legendary-dark.svg"]:
            self.assertTrue((ROOT / "docs" / f).exists(), f)


if __name__ == "__main__":
    unittest.main()
