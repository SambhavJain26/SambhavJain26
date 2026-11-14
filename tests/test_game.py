import json
import random
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from game import engine, play, render

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "game" / "bugs.json").read_text(encoding="utf-8"))
CH = json.loads((ROOT / "game" / "challenges.json").read_text(encoding="utf-8"))
BUG_IDS = {b["id"] for b in DATA["bugs"]}
NOW = datetime(2026, 11, 14, 10, tzinfo=timezone.utc)
AT = NOW.isoformat()


def start(state, login="hunter", n=1, seed=1, mode=None, bug=None):
    r = engine.start_encounter(state, DATA, CH, login, AT, n, random.Random(seed))
    if r["status"] == "encounter" and (mode or bug):  # pin the roll for deterministic tests
        enc = state["encounters"][str(n)]
        enc["mode"] = mode or enc["mode"]
        enc["bug"] = bug or enc["bug"]
        enc["cid"] = engine.challenge_for(CH, enc["mode"], enc["bug"])["id"]
        bug_obj = next(b for b in DATA["bugs"] if b["id"] == enc["bug"])
        if enc["mode"] == "report":
            enc["options"] = engine.report_options(DATA["bugs"], bug_obj, random.Random(seed))
        else:
            enc.pop("options", None)
    return r


def good(state, n=1):
    enc = state["encounters"][str(n)]
    ch = next(c for c in CH[enc["mode"]] if c["id"] == enc["cid"])
    return engine.LETTERS[enc["options"].index(ch["bug"])] if enc["mode"] == "report" else str(ch["answer"][0])


def bad(state, n=1):
    enc = state["encounters"][str(n)]
    ch = next(c for c in CH[enc["mode"]] if c["id"] == enc["cid"])
    if enc["mode"] == "report":
        return next(engine.LETTERS[i] for i, o in enumerate(enc["options"]) if o != ch["bug"])
    return str(next(i for i in range(1, len(ch["lines"]) + 1) if i not in ch["answer"]))


def say(state, body, login="hunter", n=1, cid="x"):
    return engine.answer_encounter(state, DATA, CH, n, cid, login, body, AT)


class ChallengeBank(unittest.TestCase):
    def test_one_report_and_one_code_challenge_per_bug(self):
        for mode in engine.MODES:
            self.assertEqual(sorted(c["bug"] for c in CH[mode]), sorted(BUG_IDS), mode)

    def test_every_challenge_has_text_hint_and_explanation(self):
        for c in CH["report"]:
            self.assertTrue(c["text"] and c["hint"] and c["explain"], c["id"])
        for c in CH["code"]:
            self.assertTrue(c["hint"] and c["explain"], c["id"])

    def test_code_answers_point_at_real_lines(self):
        for c in CH["code"]:
            self.assertTrue(3 <= len(c["lines"]) <= 9, c["id"])
            self.assertTrue(all(1 <= a <= len(c["lines"]) for a in c["answer"]), c["id"])
            self.assertLess(len(c["answer"]), len(c["lines"]), c["id"])


class Inputs(unittest.TestCase):
    def test_titles(self):
        self.assertEqual(engine.classify_title("bughunt: catch"), "catch")
        self.assertEqual(engine.classify_title("  BugHunt :CATCH "), "catch")
        self.assertEqual(engine.classify_title("bughunt: catch; rm -rf /"), "unknown")
        self.assertIsNone(engine.classify_title("Typo in README"))
        self.assertIsNone(engine.classify_title(None))

    def test_answers(self):
        for body, want in [("b", "B"), (" C. ", "C"), ("3", "3"), ("12)", "12")]:
            self.assertEqual(engine.parse_answer(body), want, body)
        for body in ["E", "line 3", "B because typo", "", None, "1" * 30, "$(whoami)"]:
            self.assertIsNone(engine.parse_answer(body), body)

    def test_logins(self):
        self.assertTrue(engine.valid_login("octocat"))
        for bad_login in ["", "-ab", "ab-", "github-actions[bot]", "x" * 40, None]:
            self.assertFalse(engine.valid_login(bad_login))


class Luck(unittest.TestCase):
    def test_rarity_roll_follows_weights(self):
        rarity = {b["id"]: b["rarity"] for b in DATA["bugs"]}
        counts = Counter()
        rng = random.Random(3)
        for i in range(20000):
            s = engine.initial_state(DATA["bugs"])
            r = engine.start_encounter(s, DATA, CH, f"u{i % 500}", AT, i, rng)
            counts[rarity[r["bug"]["id"]]] += 1
        self.assertAlmostEqual(counts["common"] / 20000, 0.48, delta=0.02)
        self.assertAlmostEqual(counts["legendary"] / 20000, 0.02, delta=0.006)

    def test_report_decoys_share_the_rarity_and_legendary_is_always_code(self):
        bugs = {b["id"]: b for b in DATA["bugs"]}
        for bug in DATA["bugs"]:
            if bug["rarity"] in ("common", "uncommon", "rare"):
                opts = engine.report_options(DATA["bugs"], bug, random.Random(1))
                self.assertEqual(len(opts), 4)
                self.assertIn(bug["id"], opts)
                self.assertEqual({bugs[o]["rarity"] for o in opts}, {bug["rarity"]}, bug["id"])
        rng = random.Random(9)
        for i in range(3000):
            s = engine.initial_state(DATA["bugs"])
            r = engine.start_encounter(s, DATA, CH, "u", AT, i, rng)
            if r["bug"]["rarity"] == "legendary":
                self.assertEqual(r["mode"], "code")

    def test_both_modes_appear(self):
        s = engine.initial_state(DATA["bugs"])
        rng = random.Random(4)
        modes = {engine.start_encounter(s, DATA, CH, f"u{i}", AT, i, rng)["mode"] for i in range(40)}
        self.assertEqual(modes, {"report", "code"})


class Skill(unittest.TestCase):
    def test_correct_answer_catches_with_discoverer_bonus(self):
        s = engine.initial_state(DATA["bugs"])
        start(s, mode="report", bug="typo")
        r = say(s, good(s))
        self.assertEqual(r["status"], "caught")
        self.assertEqual(r["points"], 1 + engine.DISCOVERER_BONUS)
        self.assertTrue(r["first_ever"])
        self.assertEqual(s["counts"]["typo"], 1)
        self.assertNotIn("1", s["encounters"])

    def test_code_is_double_points(self):
        s = engine.initial_state(DATA["bugs"])
        s["counts"]["null-pointer"] = 1  # not the first ever, so no bonus
        start(s, mode="code", bug="null-pointer")
        r = say(s, good(s))
        self.assertEqual(r["points"], 5 * engine.CODE_MULTIPLIER)

    def test_three_wrong_answers_and_it_escapes(self):
        s = engine.initial_state(DATA["bugs"])
        start(s, mode="code", bug="off-by-one")
        wrong_answer = bad(s)
        self.assertEqual(say(s, wrong_answer, cid="a")["tries_left"], 2)
        self.assertEqual(say(s, wrong_answer, cid="b")["tries_left"], 1)
        self.assertEqual(say(s, wrong_answer, cid="c")["status"], "escaped")
        self.assertNotIn("1", s["encounters"])
        self.assertEqual(s["total"], 0)

    def test_only_the_starter_counts_and_chatter_is_ignored(self):
        s = engine.initial_state(DATA["bugs"])
        start(s, mode="report", bug="typo")
        self.assertIsNone(say(s, good(s), login="someone-else", cid="a"))
        self.assertIsNone(say(s, "is it the typo one?", cid="b"))
        self.assertIsNone(say(s, good(s), cid="b"))  # same comment id twice: ignored
        self.assertEqual(say(s, "Z9", cid="c"), None)
        self.assertEqual(say(s, "D" if good(s) != "D" else "C", cid="d")["status"], "wrong")

    def test_out_of_range_answers_do_not_cost_a_try(self):
        s = engine.initial_state(DATA["bugs"])
        start(s, mode="code", bug="typo")
        r = say(s, "9")
        self.assertEqual(r["status"], "invalid")
        self.assertEqual(s["encounters"]["1"]["tries"], 0)

    def test_daily_limit_and_duplicates(self):
        s = engine.initial_state(DATA["bugs"])
        for i in range(engine.DAILY_LIMIT):
            self.assertEqual(start(s, n=i + 1)["status"], "encounter")
        self.assertEqual(start(s, n=99)["status"], "limit")
        self.assertEqual(start(s, n=1)["status"], "duplicate")

    def test_unanswered_encounters_expire(self):
        s = engine.initial_state(DATA["bugs"])
        start(s)
        self.assertEqual(engine.expire_encounters(s, NOW + timedelta(hours=1)), [])
        self.assertEqual(engine.expire_encounters(s, NOW + timedelta(hours=25)), [1])
        self.assertEqual(s["encounters"], {})


class Runner(unittest.TestCase):
    def test_full_flow_through_process(self):
        s = engine.initial_state(DATA["bugs"])
        issues = [{"number": 7, "title": "bughunt: catch", "author": {"login": "ada-l"}, "createdAt": AT},
                  {"number": 8, "title": "Bug in your site", "author": {"login": "x"}, "createdAt": AT},
                  {"number": 9, "title": "bughunt: hi", "author": {"login": "y"}, "createdAt": AT}]
        out = play.process(issues, lambda n: [], s, DATA, CH, random.Random(2), NOW)
        self.assertEqual([(o["issue"], o["close"]) for o in out], [(7, False), (9, True)])
        self.assertIn("A wild", out[0]["body"])
        comments = [{"id": "c1", "author": {"login": "github-actions"}, "body": "A", "createdAt": AT},
                     {"id": "c2", "author": {"login": "ada-l"}, "body": good(s, 7), "createdAt": AT}]
        out = play.process(issues[:1], lambda n: comments, s, DATA, CH, random.Random(2), NOW)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["close"])
        self.assertIn("Caught it!", out[0]["body"])
        self.assertEqual(s["total"], 1)
        out = play.process(issues[:1], lambda n: comments, s, DATA, CH, random.Random(2), NOW)
        self.assertEqual(out, [{"issue": 7, "body": None, "close": True}])  # finished: only close

    def test_encounter_reply_shows_the_challenge(self):
        for mode in engine.MODES:
            s = engine.initial_state(DATA["bugs"])
            start(s, mode=mode, bug="timezone-bug")
            r = {"bug": next(b for b in DATA["bugs"] if b["id"] == "timezone-bug"), "mode": mode,
                 "challenge": engine.challenge_for(CH, mode, "timezone-bug"),
                 "options": s["encounters"]["1"].get("options")}
            body = render.reply_encounter(r, DATA)
            ch = r["challenge"]
            right = (engine.LETTERS[r["options"].index(ch["bug"])] if mode == "report" else str(ch["answer"][0]))
            self.assertNotIn(f"for example `{right}`", body)  # the example never gives the answer away
            self.assertIn("Uncommon", body)
            self.assertIn("Reply with just the", body)
            if mode == "code":
                self.assertIn("```python", body)
            else:
                self.assertIn("**A.**", body)


class ReadmeSection(unittest.TestCase):
    def test_empty_and_busy_board(self):
        s = engine.initial_state(DATA["bugs"])
        sec = render.section(s, DATA)
        self.assertIn("issues/new?title=bughunt%3A%20catch", sec)
        self.assertIn("No hunters yet", sec)
        self.assertEqual(sec.count('alt="Undiscovered bug"'), len(DATA["bugs"]))
        start(s, login="ada-l", mode="report", bug="typo")
        say(s, good(s), login="ada-l")
        sec = render.section(s, DATA)
        self.assertIn("Top hunters", sec)
        self.assertIn("@ada-l", sec)

    def test_readme_markers_and_anchors(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for needle in [render.START, render.END, '<a name="bug-hunt"></a>', '<a name="selected-work"></a>',
                       '<a name="tools"></a>', 'href="#bug-hunt"']:
            self.assertIn(needle, readme)
        with self.assertRaises(ValueError):
            render.replace_section("no markers", "x")


if __name__ == "__main__":
    unittest.main()
