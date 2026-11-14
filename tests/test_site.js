// Unit tests for the in-browser game rules (docs/game.js). Run: node tests/test_site.js
"use strict";
const assert = require("assert");
const path = require("path");
const fs = require("fs");
const rules = require(path.join(__dirname, "..", "docs", "game.js"));

const root = path.join(__dirname, "..");
const DATA = JSON.parse(fs.readFileSync(path.join(root, "docs", "data", "bugs.json"), "utf8"));
const CH = JSON.parse(fs.readFileSync(path.join(root, "docs", "data", "challenges.json"), "utf8"));
const SRC = JSON.parse(fs.readFileSync(path.join(root, "game", "bugs.json"), "utf8"));

function seeded(seed) { // small deterministic PRNG (mulberry32)
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const byId = Object.fromEntries(DATA.bugs.map((b) => [b.id, b]));
let passed = 0;
function test(name, fn) { fn(); passed++; console.log("ok -", name); }

test("docs data is in sync with game/ (run tools/build_site.py)", () => {
  assert.deepStrictEqual(DATA, SRC);
});

test("rarity roll follows the weights", () => {
  const rnd = seeded(1), counts = {};
  for (let i = 0; i < 20000; i++) { const b = rules.rollBug(DATA.bugs, rnd); counts[b.rarity] = (counts[b.rarity] || 0) + 1; }
  assert(Math.abs(counts.common / 20000 - 0.48) < 0.02, "common " + counts.common);
  assert(Math.abs(counts.legendary / 20000 - 0.02) < 0.006, "legendary " + counts.legendary);
});

test("legendary is always a code challenge; others get both modes", () => {
  const rnd = seeded(2), legendary = DATA.bugs.find((b) => b.rarity === "legendary");
  for (let i = 0; i < 50; i++) assert.strictEqual(rules.pickMode(DATA.bugs, legendary, rnd), "code");
  const modes = new Set();
  for (let i = 0; i < 50; i++) modes.add(rules.pickMode(DATA.bugs, byId.typo, rnd));
  assert.deepStrictEqual([...modes].sort(), ["code", "report"]);
});

test("report decoys share the rarity, so it never gives the answer away", () => {
  const rnd = seeded(3);
  for (const bug of DATA.bugs.filter((b) => ["common", "uncommon", "rare"].includes(b.rarity))) {
    const opts = rules.reportOptions(DATA.bugs, bug, rnd);
    assert.strictEqual(opts.length, 4);
    assert(opts.includes(bug.id));
    assert(opts.every((o) => byId[o].rarity === bug.rarity), bug.id);
  }
});

test("every bug has a report and a code challenge", () => {
  for (const b of DATA.bugs) {
    assert(rules.challengeFor(CH, "report", b.id), b.id);
    assert(rules.challengeFor(CH, "code", b.id), b.id);
  }
});

test("right answer catches, with double points for code", () => {
  const enc = { bug: byId["null-pointer"], mode: "code", challenge: rules.challengeFor(CH, "code", "null-pointer"), tries: 0, done: false };
  const r = rules.answer(enc, DATA, enc.challenge.answer[0]);
  assert.strictEqual(r.status, "caught");
  assert.strictEqual(r.points, 5 * rules.CODE_MULTIPLIER);
  assert.strictEqual(rules.answer(enc, DATA, 1).status, "done");
});

test("three wrong answers and the bug escapes", () => {
  const ch = rules.challengeFor(CH, "report", "typo");
  const enc = { bug: byId.typo, mode: "report", challenge: ch, tries: 0, done: false,
    options: ["typo", "missing-semicolon", "trailing-whitespace", "unclosed-bracket"] };
  assert.deepStrictEqual(rules.answer(enc, DATA, 1), { status: "wrong", triesLeft: 2 });
  assert.deepStrictEqual(rules.answer(enc, DATA, 2), { status: "wrong", triesLeft: 1 });
  assert.strictEqual(rules.answer(enc, DATA, 3).status, "escaped");
});

test("new encounters are well-formed", () => {
  const rnd = seeded(4);
  for (let i = 0; i < 300; i++) {
    const e = rules.newEncounter(DATA, CH, rnd);
    assert(e.challenge && e.challenge.bug === e.bug.id);
    if (e.mode === "report") assert(e.options.includes(e.bug.id));
  }
});

test("leaderboard link matches the bot's title pattern", () => {
  const url = rules.recordUrl("timezone-bug", "code");
  assert(url.startsWith("https://github.com/SambhavJain26/SambhavJain26/issues/new?title="));
  assert(decodeURIComponent(url).includes("title=bughunt: record timezone-bug code&"));
});

console.log(`\n${passed} tests passed`);
