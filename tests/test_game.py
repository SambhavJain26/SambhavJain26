import json
import unittest
from pathlib import Path

from game import engine, play, render

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "game" / "bugs.json").read_text(encoding="utf-8"))
CH = json.loads((ROOT / "game" / "challenges.json").read_text(encoding="utf-8"))
BUG_IDS = {b["id"] for b in DATA["bugs"]}
DAY = "2026-11-14"


def fresh():
    return engine.initial_state(DATA["bugs"], CH, DAY)


def issue(n, title, login="hunter", at=f"{DAY}T10:00:00Z"):
    return {"number": n, "title": title, "author": {"login": login}, "createdAt": at}


def answer(state, mode, ans, login="hunter", n=1, at=f"{DAY}T10:00:00Z"):
    cid = state["current"][mode]["id"]
    return engine.apply_answer(state, DATA, CH, login, at, n, mode, cid, str(ans))


def right(state, mode):
    ch = engine.current_challenge(state, CH, mode)
    return ch["bug"] if mode == "report" else ch["answer"][0]


def wrong(state, mode):
    ch = engine.current_challenge(state, CH, mode)
    if mode == "report":
        return next(o for o in ch["options"] if o != ch["bug"])
    return next(i for i in range(1, len(ch["lines"]) + 1) if i not in ch["answer"])


class ChallengeBank(unittest.TestCase):
    def test_one_report_and_one_code_challenge_per_bug(self):
        for mode in engine.MODES:
            self.assertEqual(sorted(c["bug"] for c in CH[mode]), sorted(BUG_IDS), mode)
            ids = [c["id"] for c in CH[mode]]
            self.assertEqual(len(ids), len(set(ids)), mode)

    def test_reports_are_answerable(self):
        for c in CH["report"]:
            self.assertEqual(len(c["options"]), 4, c["id"])
            self.assertIn(c["bug"], c["options"], c["id"])
            self.assertTrue(set(c["options"]) <= BUG_IDS, c["id"])
            self.assertTrue(c["hint"] and c["explain"], c["id"])

    def test_code_answers_point_at_real_lines(self):
        for c in CH["code"]:
            self.assertIn(c["lang"], ("python", "javascript"), c["id"])
            self.assertTrue(3 <= len(c["lines"]) <= 10, c["id"])
            self.assertTrue(all(1 <= a <= len(c["lines"]) for a in c["answer"]), c["id"])
            self.assertLess(len(c["answer"]), len(c["lines"]), c["id"])

    def test_ids_fit_the_title_pattern(self):
        for mode in engine.MODES:
            for c in CH[mode]:
                ans = c["bug"] if mode == "report" else str(c["answer"][0])
                parsed = engine.parse_title(f"bughunt: {mode} {c['id']} {ans}")
                self.assertEqual(parsed and parsed["kind"], "answer", c["id"])


class Titles(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(engine.parse_title("bughunt: code c05 3"),
                         {"kind": "answer", "mode": "code", "cid": "c05", "answer": "3"})
        self.assertEqual(engine.parse_title("BugHunt:Report R08 Timezone-Bug")["answer"], "timezone-bug")
        self.assertEqual(engine.parse_title("bughunt: code c05 3; rm -rf /"), {"kind": "unknown"})
        self.assertEqual(engine.parse_title("bughunt: catch"), {"kind": "unknown"})
        self.assertIsNone(engine.parse_title("Typo in README"))
        self.assertIsNone(engine.parse_title(None))

    def test_login_validation(self):
        for ok in ["octocat", "a", "ab-cd"]:
            self.assertTrue(engine.valid_login(ok))
        for bad in ["", "-ab", "ab-", "a b", "github-actions[bot]", "x" * 40, None]:
            self.assertFalse(engine.valid_login(bad))


class Playing(unittest.TestCase):
    def test_correct_report_catches_bug(self):
        s = fresh()
        r = answer(s, "report", right(s, "report"))
        self.assertEqual(r["status"], "caught")
        self.assertTrue(r["first_solver"] and r["first_ever"])
        bug = r["bug"]
        self.assertEqual(r["points"], DATA["rarities"][bug["rarity"]]["points"] + engine.FIRST_SOLVER_BONUS)
        self.assertEqual(s["counts"][bug["id"]], 1)

    def test_code_is_double_points(self):
        s = fresh()
        answer(s, "code", right(s, "code"), login="first", n=1)
        r = answer(s, "code", right(s, "code"), login="second", n=2)
        self.assertEqual(r["points"], DATA["rarities"][r["bug"]["rarity"]]["points"] * engine.CODE_MULTIPLIER)
        self.assertFalse(r["first_solver"])

    def test_wrong_answers_use_tries(self):
        s = fresh()
        r1 = answer(s, "code", wrong(s, "code"), n=1)
        self.assertEqual((r1["status"], r1["tries_left"]), ("wrong", 2))
        answer(s, "code", wrong(s, "code"), n=2)
        r3 = answer(s, "code", wrong(s, "code"), n=3)
        self.assertEqual(r3["status"], "out_of_tries")
        r4 = answer(s, "code", right(s, "code"), n=4)
        self.assertEqual(r4["status"], "out_of_tries")
        self.assertEqual(s["total"], 0)

    def test_already_solved_and_duplicates(self):
        s = fresh()
        answer(s, "report", right(s, "report"), n=1)
        self.assertEqual(answer(s, "report", right(s, "report"), n=2)["status"], "already_solved")
        self.assertEqual(answer(s, "report", right(s, "report"), n=2)["status"], "duplicate")
        self.assertEqual(s["total"], 1)

    def test_stale_and_invalid_options(self):
        s = fresh()
        r = engine.apply_answer(s, DATA, CH, "h", f"{DAY}T10:00:00Z", 1, "report", "r99", "typo")
        self.assertEqual(r["status"], "stale")
        self.assertEqual(answer(s, "code", 99, n=2)["status"], "invalid_option")
        self.assertEqual(answer(s, "report", "not-a-bug", n=3)["status"], "invalid_option")

    def test_daily_limit(self):
        s = fresh()
        for i in range(engine.DAILY_LIMIT):
            answer(s, "report", "x" if i % 2 else wrong(s, "report"), login=f"u{i}", n=100 + i)
        for i in range(engine.DAILY_LIMIT):
            s["hunters"].setdefault("spam", {"catches": 0, "points": 0, "best": None, "day": DAY, "today": 0})
        s["hunters"]["spam"]["today"] = engine.DAILY_LIMIT
        self.assertEqual(answer(s, "report", right(s, "report"), login="spam", n=999)["status"], "limit")

    def test_rotation_after_three_solves_and_daily(self):
        s = fresh()
        first = s["current"]["code"]["id"]
        for i, who in enumerate(["a", "b", "c"]):
            answer(s, "code", right(s, "code"), login=who, n=i + 1)
        self.assertEqual(engine.rotate_if_needed(s, CH, DAY), ["code"])
        self.assertNotEqual(s["current"]["code"]["id"], first)
        self.assertNotIn(first, s["tries"])
        self.assertEqual(engine.rotate_if_needed(s, CH, DAY), [])
        self.assertEqual(sorted(engine.rotate_if_needed(s, CH, "2026-11-15")), ["code", "report"])

    def test_rotation_wraps_around(self):
        s = fresh()
        for d in range(len(CH["report"])):
            engine.rotate_if_needed(s, CH, f"2027-01-{d + 1:02d}")
        self.assertEqual(s["current"]["report"]["id"], CH["report"][0]["id"])


class ProcessingAndRendering(unittest.TestCase):
    def test_process_ignores_unrelated_and_answers_bad_ones(self):
        s = fresh()
        rep = s["current"]["report"]["id"]
        issues = [issue(1, f"bughunt: report {rep} {right(s, 'report')}"),
                  issue(2, "Bug in your site"),
                  issue(3, "bughunt: hello"),
                  issue(4, f"bughunt: report {rep} typo", login="evil[bot]")]
        outbox = play.process_issues(issues, s, DATA, CH)
        self.assertEqual([o["issue"] for o in outbox], [1, 3, 4])
        self.assertIn("Correct!", outbox[0]["body"])
        self.assertIn("couldn't read", outbox[1]["body"])
        self.assertEqual(s["total"], 1)

    def test_section_shows_both_challenges_with_working_links(self):
        s = fresh()
        sec = render.section(s, DATA, CH)
        self.assertIn("No hunters yet", sec)
        self.assertEqual(sec.count('alt="Undiscovered bug"'), len(DATA["bugs"]))
        rep = engine.current_challenge(s, CH, "report")
        code = engine.current_challenge(s, CH, "code")
        for opt in rep["options"]:
            self.assertIn(render.answer_url("report", rep["id"], opt).replace("&", "&"), sec)
        self.assertEqual(sec.count(f"bughunt%3A%20code%20{code['id']}%20"), len(code["lines"]))
        self.assertNotIn("<script", sec.lower())

    def test_code_is_escaped(self):
        s = fresh()
        s["current"]["code"]["id"] = "c07"
        sec = render.section(s, DATA, CH)
        self.assertIn("&lt;&lt;&lt;&lt;&lt;&lt;&lt; HEAD", sec)

    def test_board_appears_after_first_catch(self):
        s = fresh()
        answer(s, "report", right(s, "report"), login="ada-l")
        sec = render.section(s, DATA, CH)
        self.assertIn("Top hunters", sec)
        self.assertIn("@ada-l", sec)

    def test_every_reply_renders(self):
        s = fresh()
        r = answer(s, "report", right(s, "report"))
        self.assertIn("Why:", render.reply_for(r, DATA))
        for status in ["wrong", "out_of_tries", "already_solved", "stale", "invalid_option", "limit", "duplicate"]:
            fake = {"status": status, "challenge": CH["code"][0], "tries_left": 1, "limit": 15}
            self.assertTrue(render.reply_for(fake, DATA))

    def test_replace_section_and_readme_markers(self):
        out = render.replace_section(f"a\n{render.START}\nPLACEHOLDER\n{render.END}\nb", "X")
        self.assertEqual(out, "a\nX\nb")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(render.START, readme)
        self.assertIn(render.END, readme)
        with self.assertRaises(ValueError):
            render.replace_section("no markers", "x")


if __name__ == "__main__":
    unittest.main()
