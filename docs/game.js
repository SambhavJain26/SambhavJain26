/* Bug Hunt: the instant, in-browser version.
 * Luck finds the bug (a weighted rarity roll), skill catches it (solve its challenge).
 * The pure rules at the top are also unit-tested with Node (tests/test_site.js).
 */
(function (root) {
  "use strict";

  // ---------------------------------------------------------------- rules (pure)
  var LETTERS = "ABCD";
  var RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"];
  var MAX_TRIES = 3;
  var CODE_MULTIPLIER = 2;

  function rank(r) { return RARITY_ORDER.indexOf(r); }

  function rollBug(bugs, rnd) {
    var total = bugs.reduce(function (s, b) { return s + Number(b.weight); }, 0);
    var x = rnd() * total;
    for (var i = 0; i < bugs.length; i++) {
      x -= Number(bugs[i].weight);
      if (x < 0) return bugs[i];
    }
    return bugs[bugs.length - 1];
  }

  function shuffle(list, rnd) {
    var a = list.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(rnd() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  // A bug that's alone in its rarity (the legendary) always comes as code:
  // the rarity is announced, so a multiple-choice report would give it away.
  function pickMode(bugs, bug, rnd) {
    var alone = bugs.filter(function (b) { return b.rarity === bug.rarity; }).length === 1;
    return alone ? "code" : (rnd() < 0.5 ? "report" : "code");
  }

  // The right bug plus 3 decoys of the same rarity where possible, so the
  // announced rarity never reveals the answer.
  function reportOptions(bugs, bug, rnd) {
    var r = rank(bug.rarity);
    var others = shuffle(bugs.filter(function (b) { return b.id !== bug.id; }), rnd);
    others.sort(function (a, b) { return Math.abs(rank(a.rarity) - r) - Math.abs(rank(b.rarity) - r); });
    var ids = [bug.id].concat(others.slice(0, LETTERS.length - 1).map(function (b) { return b.id; }));
    return shuffle(ids, rnd);
  }

  function challengeFor(challenges, mode, bugId) {
    return challenges[mode].filter(function (c) { return c.bug === bugId; })[0];
  }

  function newEncounter(data, challenges, rnd) {
    var bug = rollBug(data.bugs, rnd);
    var mode = pickMode(data.bugs, bug, rnd);
    var enc = { bug: bug, mode: mode, challenge: challengeFor(challenges, mode, bug.id), tries: 0, done: false };
    if (mode === "report") enc.options = reportOptions(data.bugs, bug, rnd);
    return enc;
  }

  // answer: a letter index (report) or a 1-based line number (code).
  // Returns {status: "caught"|"wrong"|"escaped", triesLeft, points}.
  function answer(enc, data, value) {
    if (enc.done) return { status: "done" };
    var ok = enc.mode === "report"
      ? enc.options[value] === enc.bug.id
      : enc.challenge.answer.indexOf(value) !== -1;
    if (ok) {
      enc.done = true;
      var pts = data.rarities[enc.bug.rarity].points * (enc.mode === "code" ? CODE_MULTIPLIER : 1);
      return { status: "caught", points: pts };
    }
    enc.tries += 1;
    var left = MAX_TRIES - enc.tries;
    if (left <= 0) { enc.done = true; return { status: "escaped", triesLeft: 0 }; }
    return { status: "wrong", triesLeft: left };
  }

  function recordUrl(bugId, mode) {
    var title = "bughunt: record " + bugId + " " + mode;
    var body = "Just press **Create** without changing the title. The Bug Hunt bot will add this catch to the " +
      "leaderboard on the profile in about a minute, then close this issue. 🐛";
    return "https://github.com/SambhavJain26/SambhavJain26/issues/new?title=" + encodeURIComponent(title) +
      "&body=" + encodeURIComponent(body);
  }

  var rules = { LETTERS: LETTERS, MAX_TRIES: MAX_TRIES, CODE_MULTIPLIER: CODE_MULTIPLIER, rollBug: rollBug,
    pickMode: pickMode, reportOptions: reportOptions, challengeFor: challengeFor, newEncounter: newEncounter,
    answer: answer, recordUrl: recordUrl };
  if (typeof module !== "undefined" && module.exports) { module.exports = rules; return; }

  // ---------------------------------------------------------------- browser UI
  var doc = root.document;
  var $ = function (id) { return doc.getElementById(id); };
  var reduceMotion = root.matchMedia && root.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var DATA, CH, enc;
  var KEY = "bughunt.v1";

  function load() {
    try { return JSON.parse(root.localStorage.getItem(KEY)) || { counts: {}, points: 0, catches: 0 }; }
    catch (e) { return { counts: {}, points: 0, catches: 0 }; }
  }
  function save(s) { try { root.localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* private mode */ } }
  var me = load();

  function el(tag, attrs, children) {
    var n = doc.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "class") n.className = attrs[k];
      else if (k.indexOf("on") === 0) n.addEventListener(k.slice(2), attrs[k]);
      else n.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? doc.createTextNode(c) : c); });
    return n;
  }
  function names() { var m = {}; DATA.bugs.forEach(function (b) { m[b.id] = b.name; }); return m; }
  function rarity(b) { return DATA.rarities[b.rarity]; }
  function art(id, theme) { return "art/" + id + "-" + theme + ".svg"; }
  function pic(id, alt, cls) {
    var dark = root.matchMedia && root.matchMedia("(prefers-color-scheme: dark)").matches;
    return el("img", { src: art(id, dark ? "dark" : "light"), alt: alt, class: cls || "" });
  }

  function renderDex() {
    var grid = $("dex"); grid.textContent = "";
    var found = 0;
    DATA.bugs.forEach(function (b) {
      var n = me.counts[b.id] || 0;
      if (n) found++;
      grid.appendChild(el("div", { class: "tile" + (n ? "" : " locked") }, [
        n ? pic(b.id, b.name) : pic("unknown-" + b.rarity, "Undiscovered " + rarity(b).label + " bug"),
        el("div", { class: "tname", text: n ? b.name : "???" }),
        el("div", { class: "tmeta", text: rarity(b).label + (n ? " · ×" + n : "") })
      ]));
    });
    $("stat-found").textContent = found + " / " + DATA.bugs.length;
    $("stat-caught").textContent = me.catches;
    $("stat-points").textContent = me.points;
  }

  function setStage(node) { var s = $("stage"); s.textContent = ""; s.appendChild(node); }

  function idle() {
    setStage(el("div", { class: "idle" }, [
      el("p", { class: "kicker", text: "Luck finds the bug · skill catches it" }),
      el("button", { class: "catch", onclick: roll }, [el("span", { class: "net", "aria-hidden": "true", text: "🪲" }), "Catch a bug"]),
      el("p", { class: "muted", text: "Commons are everywhere. Legendaries almost never show up." })
    ]));
  }

  function roll() {
    enc = newEncounter(DATA, CH, Math.random);
    var slot = el("div", { class: "slot", "aria-live": "polite" }, [el("span", { class: "slotword", text: "Rolling…" })]);
    setStage(el("div", { class: "rolling" }, [el("p", { class: "kicker", text: "Something is moving in the code…" }), slot]));
    var order = ["common", "uncommon", "rare", "epic", "legendary"];
    var i = 0, ticks = reduceMotion ? 1 : 14;
    (function tick() {
      var key = i < ticks - 1 ? order[i % order.length] : enc.bug.rarity;
      var r = DATA.rarities[key];
      slot.firstChild.textContent = r.label;
      slot.style.setProperty("--c", r.color);
      i++;
      if (i < ticks) setTimeout(tick, 60 + i * 12);
      else setTimeout(showChallenge, reduceMotion ? 0 : 450);
    })();
  }

  function triesDots() {
    var d = el("span", { class: "tries", "aria-label": (rules.MAX_TRIES - enc.tries) + " tries left" });
    for (var i = 0; i < rules.MAX_TRIES; i++) d.appendChild(el("i", { class: i < rules.MAX_TRIES - enc.tries ? "on" : "" }));
    return d;
  }

  function showChallenge() {
    var r = rarity(enc.bug), ch = enc.challenge, nm = names();
    var head = el("div", { class: "enc-head" }, [
      pic("unknown-" + enc.bug.rarity, "An undiscovered " + r.label + " bug", "mystery"),
      el("div", {}, [
        el("p", { class: "kicker", text: "A wild bug appeared" }),
        el("h2", {}, [el("span", { class: "rar", style: "--c:" + r.color, text: r.label }), " bug"]),
        el("p", { class: "muted", text: enc.mode === "code" ? "Code challenge · double points" : "Bug report" })
      ]),
      triesDots()
    ]);
    var body;
    if (enc.mode === "report") {
      body = el("div", {}, [
        el("blockquote", { text: "“" + ch.text + "”" }),
        el("p", { class: "q", text: "Which bug did this?" }),
        el("div", { class: "opts" }, enc.options.map(function (id, i) {
          return el("button", { class: "opt", onclick: function (e) { pick(i, e.currentTarget); } },
            [el("b", { text: rules.LETTERS[i] }), nm[id]]);
        }))
      ]);
    } else {
      body = el("div", {}, [
        el("p", { class: "q", text: "Which line has the bug? Click it." }),
        el("div", { class: "code", role: "list" }, ch.lines.map(function (line, i) {
          return el("button", { class: "line", role: "listitem", onclick: function (e) { pick(i + 1, e.currentTarget); } },
            [el("span", { class: "ln", text: String(i + 1) }), el("code", { text: line || " " })]);
        })),
        el("p", { class: "muted small", text: ch.lang === "python" ? "Python" : "JavaScript" })
      ]);
    }
    setStage(el("div", { class: "challenge" }, [head, body, el("p", { id: "feedback", class: "feedback", "aria-live": "polite" })]));
  }

  function pick(value, button) {
    var res = answer(enc, DATA, value);
    if (res.status === "caught") return caught(res);
    if (res.status === "escaped") return escaped();
    button.disabled = true;
    button.classList.add("nope");
    var fb = $("feedback");
    fb.textContent = "Not there. Hint: " + enc.challenge.hint + " (" + res.triesLeft + " " + (res.triesLeft === 1 ? "try" : "tries") + " left)";
    fb.classList.remove("shake"); void fb.offsetWidth; fb.classList.add("shake");
    var dots = doc.querySelector(".tries");
    dots.parentNode.replaceChild(triesDots(), dots);
  }

  function caught(res) {
    var b = enc.bug, r = rarity(b);
    var first = !me.counts[b.id];
    me.counts[b.id] = (me.counts[b.id] || 0) + 1;
    me.catches += 1; me.points += res.points;
    save(me); renderDex();
    setStage(el("div", { class: "result" }, [
      pic(b.id, b.name, "caught-art"),
      el("div", {}, [
        el("p", { class: "kicker", text: first ? "New in your Bugdex!" : "Caught again" }),
        el("h2", { text: b.name }),
        el("p", {}, [el("span", { class: "rar", style: "--c:" + r.color, text: r.label }), " · +" + res.points + " pts" + (enc.mode === "code" ? " (double for code)" : "")]),
        el("p", {}, [el("b", { text: "Why: " }), enc.challenge.explain]),
        el("p", { class: "flavor", text: b.flavor }),
        el("div", { class: "actions" }, [
          el("button", { class: "catch small", onclick: roll, text: "Catch another" }),
          el("a", { class: "ghost", href: rules.recordUrl(b.id, enc.mode) }, ["Add me to the leaderboard ↗"])
        ]),
        el("p", { class: "muted small", text: "The leaderboard lives on the GitHub profile. Adding yourself opens a pre-filled issue; press Create and the bot records your catch." })
      ])
    ]));
  }

  function escaped() {
    setStage(el("div", { class: "idle" }, [
      el("p", { class: "kicker", text: "💨 The bug escaped" }),
      el("p", { text: "It slipped away after " + rules.MAX_TRIES + " tries. There are plenty more where it came from." }),
      el("button", { class: "catch", onclick: roll, text: "Catch another" })
    ]));
  }

  function start() {
    Promise.all([fetch("data/bugs.json").then(function (r) { return r.json(); }),
                 fetch("data/challenges.json").then(function (r) { return r.json(); })])
      .then(function (res) {
        DATA = res[0]; CH = res[1];
        renderDex(); idle();
        $("reset").addEventListener("click", function () {
          if (root.confirm("Clear your Bugdex and score on this device?")) { me = { counts: {}, points: 0, catches: 0 }; save(me); renderDex(); }
        });
      })
      .catch(function () { setStage(el("p", { text: "The bugs failed to load. Try refreshing the page." })); });
  }
  doc.addEventListener("DOMContentLoaded", start);
})(typeof window !== "undefined" ? window : globalThis);
