import json
import random
import unittest
from collections import Counter
from pathlib import Path

from game import engine, play, render

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "game" / "bugs.json").read_text(encoding="utf-8"))


def issue(n, title="bughunt: catch", login="hunter", at="2026-11-14T10:00:00Z"):
    return {"number": n, "title": title, "author": {"login": login}, "createdAt": at}


class TitleAndLogin(unittest.TestCase):
    def test_catch_titles(self):
        for t in ["bughunt: catch", "BugHunt:catch", "  bughunt :  CATCH  "]:
            self.assertEqual(engine.classify_title(t), "catch", t)

    def test_unknown_and_unrelated_titles(self):
        self.assertEqual(engine.classify_title("bughunt: catch; rm -rf /"), "unknown")
        self.assertEqual(engine.classify_title("bughunt"), "unknown")
        self.assertIsNone(engine.classify_title("Typo in README"))
        self.assertIsNone(engine.classify_title(None))
        self.assertIsNone(engine.classify_title("bughunt: catch" + "x" * 300))

    def test_login_validation(self):
        for ok in ["octocat", "a", "ab-cd", "A1"]:
            self.assertTrue(engine.valid_login(ok), ok)
        for bad in ["", "-ab", "ab-", "a b", "github-actions[bot]", "x" * 40, "<script>", None]:
            self.assertFalse(engine.valid_login(bad), bad)


class Catching(unittest.TestCase):
    def setUp(self):
        self.state = engine.initial_state(DATA["bugs"])
        self.rng = random.Random(1)

    def test_weights_sum_to_100_and_rarities_exist(self):
        self.assertAlmostEqual(sum(b["weight"] for b in DATA["bugs"]), 100)
        for b in DATA["bugs"]:
            self.assertIn(b["rarity"], DATA["rarities"])
            self.assertTrue((ROOT / "game" / "art" / f"{b['id']}-light.svg").exists())
            self.assertTrue((ROOT / "game" / "art" / f"{b['id']}-dark.svg").exists())

    def test_distribution_roughly_matches_weights(self):
        counts = Counter(engine.pick_bug(DATA["bugs"], self.rng)["rarity"] for _ in range(20000))
        self.assertAlmostEqual(counts["common"] / 20000, 0.48, delta=0.02)
        self.assertAlmostEqual(counts["legendary"] / 20000, 0.02, delta=0.006)

    def test_catch_updates_state(self):
        r = engine.apply_catch(self.state, DATA, "ada", "2026-11-14T01:00:00Z", 7, self.rng)
        self.assertEqual(r["status"], "caught")
        self.assertEqual(self.state["total"], 1)
        self.assertEqual(self.state["counts"][r["bug"]["id"]], 1)
        self.assertTrue(r["first_ever"])
        self.assertEqual(self.state["hunters"]["ada"]["points"], r["points"])
        self.assertEqual(self.state["recent"][0]["issue"], 7)

    def test_same_issue_counts_once(self):
        engine.apply_catch(self.state, DATA, "ada", "2026-11-14T01:00:00Z", 7, self.rng)
        r = engine.apply_catch(self.state, DATA, "ada", "2026-11-14T01:00:00Z", 7, self.rng)
        self.assertEqual(r["status"], "duplicate")
        self.assertEqual(self.state["total"], 1)

    def test_daily_limit_resets_next_day(self):
        for i in range(engine.DAILY_LIMIT):
            engine.apply_catch(self.state, DATA, "ada", "2026-11-14T01:00:00Z", i, self.rng)
        r = engine.apply_catch(self.state, DATA, "ada", "2026-11-14T23:00:00Z", 100, self.rng)
        self.assertEqual(r["status"], "limit")
        self.assertEqual(self.state["total"], engine.DAILY_LIMIT)
        r = engine.apply_catch(self.state, DATA, "ada", "2026-11-15T00:01:00Z", 101, self.rng)
        self.assertEqual(r["status"], "caught")

    def test_best_bug_keeps_rarest(self):
        epic = next(b for b in DATA["bugs"] if b["rarity"] == "epic")
        common = next(b for b in DATA["bugs"] if b["rarity"] == "common")
        seq = iter([epic, common])
        orig = engine.pick_bug
        engine.pick_bug = lambda bugs, rng: next(seq)
        try:
            engine.apply_catch(self.state, DATA, "ada", "2026-11-14T01:00:00Z", 1, self.rng)
            engine.apply_catch(self.state, DATA, "ada", "2026-11-14T02:00:00Z", 2, self.rng)
        finally:
            engine.pick_bug = orig
        self.assertEqual(self.state["hunters"]["ada"]["best"], epic["id"])

    def test_leaderboard_order(self):
        self.state["hunters"] = {
            "b": {"catches": 3, "points": 10, "best": None, "day": "", "today": 0},
            "a": {"catches": 5, "points": 10, "best": None, "day": "", "today": 0},
            "c": {"catches": 1, "points": 25, "best": None, "day": "", "today": 0},
        }
        self.assertEqual([k for k, _ in engine.leaderboard(self.state)], ["c", "a", "b"])


class ProcessingAndRendering(unittest.TestCase):
    def test_process_ignores_unrelated_and_answers_bad_ones(self):
        state = engine.initial_state(DATA["bugs"])
        issues = [issue(1), issue(2, title="Bug in your site"), issue(3, title="bughunt: hello"),
                  issue(4, login="evil[bot]")]
        outbox = play.process_issues(issues, state, DATA, random.Random(3))
        self.assertEqual([o["issue"] for o in outbox], [1, 3, 4])
        self.assertEqual(state["total"], 1)
        self.assertIn("You caught", outbox[0]["body"])
        self.assertIn("only understand", outbox[1]["body"])

    def test_section_renders_and_replaces(self):
        state = engine.initial_state(DATA["bugs"])
        empty = render.section(state, DATA)
        self.assertIn("No hunters yet", empty)
        self.assertEqual(empty.count('alt="Undiscovered bug"'), len(DATA["bugs"]))
        for key in DATA["rarities"]:
            self.assertTrue((ROOT / "game" / "art" / f"unknown-{key}-light.svg").exists())
        play.process_issues([issue(i, login=f"h{i % 3}") for i in range(1, 15)], state, DATA, random.Random(5))
        full = render.section(state, DATA)
        self.assertIn("Top hunters", full)
        self.assertIn("@h", full)
        readme = f"intro\n{render.START}\nold\n{render.END}\noutro"
        out = render.replace_section(readme, full)
        self.assertTrue(out.startswith("intro\n") and out.endswith("\noutro"))
        self.assertNotIn("\nold\n", out)

    def test_markers_missing_raises(self):
        with self.assertRaises(ValueError):
            render.replace_section("no markers here", "x")

    def test_catch_url_is_prefilled(self):
        self.assertIn("issues/new?title=bughunt%3A%20catch", render.CATCH_URL)

    def test_readme_has_markers(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(render.START, readme)
        self.assertIn(render.END, readme)


if __name__ == "__main__":
    unittest.main()
