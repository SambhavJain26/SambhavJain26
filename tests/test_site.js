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

test("the player can pick report or code; the legendary is code only", () => {
  const legendary = DATA.bugs.find((b) => b.rarity === "legendary");
  assert.deepStrictEqual(rules.modesFor(DATA.bugs, legendary), ["code"]);
  for (const b of DATA.bugs.filter((x) => x !== legendary)) assert.deepStrictEqual(rules.modesFor(DATA.bugs, b), ["report", "code"]);
});

test("both challenges are on offer until the player chooses", () => {
  const rnd = seeded(5);
  let enc;
  do { enc = rules.newEncounter(DATA, CH, rnd); } while (enc.bug.rarity === "legendary");
  assert.strictEqual(enc.mode, null);
  assert(enc.offers.report && enc.offers.code);
  assert.strictEqual(rules.answer(enc, DATA, 0).status, "done"); // can't answer before choosing
  assert.strictEqual(rules.choose(enc, "code"), true);
  assert.strictEqual(rules.choose(enc, "report"), false); // no switching after choosing
  assert.strictEqual(enc.challenge, enc.offers.code);
  const leg = { bug: DATA.bugs.find((b) => b.rarity === "legendary"), modes: ["code"], offers: {}, mode: null };
  assert.strictEqual(rules.choose(leg, "report"), false);
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
  assert.strictEqual(rules.points(DATA, byId["null-pointer"], "report"), 5);
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
    for (const m of e.modes) assert(e.offers[m] && e.offers[m].bug === e.bug.id);
    if (e.modes.includes("report")) assert(e.options.includes(e.bug.id));
  }
});

test("every queued catch goes to the leaderboard, in titles the bot accepts", () => {
  const pending = [];
  for (let i = 0; i < 23; i++) pending.push({ bug: DATA.bugs[i % 16].id, mode: i % 2 ? "code" : "report" });
  const batches = rules.batchTitles(pending);
  assert.strictEqual(batches.reduce((n, b) => n + b.count, 0), 23); // nothing dropped
  const pattern = /^bughunt: record( [a-z][a-z-]{0,39}\/[rc])+$/;
  for (const b of batches) {
    assert(pattern.test(b.title), b.title);
    assert(b.count <= rules.MAX_PER_ISSUE);
    assert(b.title.length <= 256);
  }
  assert.strictEqual(batches[0].title.split(" ")[2], DATA.bugs[0].id + "/r");
  const url = rules.recordUrl(batches[0].title);
  assert(url.startsWith("https://github.com/SambhavJain26/SambhavJain26/issues/new?title="));
  assert(decodeURIComponent(url).includes("title=" + batches[0].title + "&"));
});

test("code challenges: answers point at real lines", () => {
  for (const c of CH.code) for (const a of c.answer) assert(a >= 1 && a <= c.lines.length && c.lines[a - 1].trim(), c.id);
});

test("syntax colours: VS Code-style tokens, and every line is kept intact", () => {
  const py = rules.tokenize("def f(x): return round(x, 2)  # done", "python");
  const kinds = Object.fromEntries(py.filter((t) => t[0]).map((t) => [t[1].trim(), t[0]]));
  assert.strictEqual(kinds.def, "kw");
  assert.strictEqual(kinds.return, "ctl");
  assert.strictEqual(kinds.f, "fn");
  assert.strictEqual(kinds.round, "fn");
  assert.strictEqual(kinds["2"], "num");
  assert.strictEqual(kinds["# done"], "com");
  const js = rules.tokenize('const greeting = "Hi, " + user.name // x', "javascript");
  assert.deepStrictEqual(js.filter((t) => t[0]).map((t) => t[0]), ["kw", "str", "com"]);
  for (const c of CH.code) for (const line of c.lines) {
    assert.strictEqual(rules.tokenize(line, c.lang).map((t) => t[1]).join(""), line, c.id + ": " + line);
  }
});

console.log(`\n${passed} tests passed`);
