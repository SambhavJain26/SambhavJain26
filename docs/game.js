/* Bug Hunt: the instant, in-browser version.
 * Luck finds the bug (a weighted rarity roll). Then the player sees both of its challenges,
 * the bug report (x1) and the code (x2), and picks one. Skill catches it.
 * Every catch is queued until the player sends the queue to the leaderboard in one issue.
 * The pure rules at the top are also unit-tested with Node (tests/test_site.js).
 */
(function (root) {
  "use strict";

  // ---------------------------------------------------------------- rules (pure)
  var LETTERS = "ABCD";
  var RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"];
  var MAX_TRIES = 3;
  var CODE_MULTIPLIER = 2;
  var MAX_PER_ISSUE = 10;   // must match game/engine.py
  var MAX_TITLE = 250;      // GitHub allows 256
  var REPO_ISSUES = "https://github.com/SambhavJain26/SambhavJain26/issues/new";

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

  // A bug that's alone in its rarity (the legendary) only offers code:
  // the rarity is announced, so a multiple-choice report would give it away.
  function modesFor(bugs, bug) {
    var alone = bugs.filter(function (b) { return b.rarity === bug.rarity; }).length === 1;
    return alone ? ["code"] : ["report", "code"];
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

  function points(data, bug, mode) {
    return data.rarities[bug.rarity].points * (mode === "code" ? CODE_MULTIPLIER : 1);
  }

  // A rolled bug with both challenges on offer; the player picks one with choose().
  function newEncounter(data, challenges, rnd) {
    var bug = rollBug(data.bugs, rnd);
    var modes = modesFor(data.bugs, bug);
    var enc = { bug: bug, modes: modes, mode: null, challenge: null, tries: 0, done: false,
      offers: {} };
    modes.forEach(function (m) { enc.offers[m] = challengeFor(challenges, m, bug.id); });
    if (modes.indexOf("report") !== -1) enc.options = reportOptions(data.bugs, bug, rnd);
    return enc;
  }

  function choose(enc, mode) {
    if (enc.mode || enc.modes.indexOf(mode) === -1) return false;
    enc.mode = mode;
    enc.challenge = enc.offers[mode];
    return true;
  }

  // answer: a letter index (report) or a 1-based line number (code).
  // Returns {status: "caught"|"wrong"|"escaped"|"done", triesLeft, points}.
  function answer(enc, data, value) {
    if (enc.done || !enc.mode) return { status: "done" };
    var ok = enc.mode === "report"
      ? enc.options[value] === enc.bug.id
      : enc.challenge.answer.indexOf(value) !== -1;
    if (ok) {
      enc.done = true;
      return { status: "caught", points: points(data, enc.bug, enc.mode) };
    }
    enc.tries += 1;
    var left = MAX_TRIES - enc.tries;
    if (left <= 0) { enc.done = true; return { status: "escaped", triesLeft: 0 }; }
    return { status: "wrong", triesLeft: left };
  }

  // Split queued catches [{bug, mode}] into issue titles the bot accepts:
  //   bughunt: record typo/r off-by-one/c ...
  function batchTitles(pending) {
    var titles = [], cur = [], curLen = 0, base = "bughunt: record".length;
    pending.forEach(function (c) {
      var token = c.bug + "/" + (c.mode === "code" ? "c" : "r");
      if (cur.length && (cur.length >= MAX_PER_ISSUE || base + curLen + 1 + token.length > MAX_TITLE)) {
        titles.push(cur); cur = []; curLen = 0;
      }
      cur.push(token); curLen += 1 + token.length;
    });
    if (cur.length) titles.push(cur);
    return titles.map(function (tokens) { return { count: tokens.length, title: "bughunt: record " + tokens.join(" ") }; });
  }

  function recordUrl(title) {
    var body = "Just press **Create** without changing the title. The Bug Hunt bot adds these catches to the " +
      "leaderboard on the profile in about a minute, then closes this issue. 🐛";
    return REPO_ISSUES + "?title=" + encodeURIComponent(title) + "&body=" + encodeURIComponent(body);
  }

  // ---------------------------------------------------------------- syntax colours (pure)
  // A small line-by-line tokenizer, VS Code style: keyword, control, string, comment,
  // number, function call, type/module. It never looks at which line is the answer.
  var WORDS = {
    python: {
      kw: "def class lambda import from as None True False and or not in is with global nonlocal async await pass del",
      ctl: "return if elif else for while try except finally raise break continue yield",
      type: "datetime timezone timedelta Path re json os subprocess threading time str int float list dict bool"
    },
    javascript: {
      kw: "const let var function new null undefined true false this typeof instanceof of in async await class",
      ctl: "return if else for while do try catch finally throw break continue switch case default",
      type: "Promise console JSON Math Object Array Date Error"
    }
  };
  function wordSet(s) { var o = {}; s.split(" ").forEach(function (w) { o[w] = true; }); return o; }
  var SETS = {};
  Object.keys(WORDS).forEach(function (lang) {
    SETS[lang] = { kw: wordSet(WORDS[lang].kw), ctl: wordSet(WORDS[lang].ctl), type: wordSet(WORDS[lang].type) };
  });

  // Returns [[type|null, text], ...] covering the whole line.
  function tokenize(line, lang) {
    var py = lang === "python", sets = SETS[py ? "python" : "javascript"];
    var re = py
      ? /(#.*$)|([rRfFbBuU]{0,2}(?:"""[\s\S]*?(?:"""|$)|'''[\s\S]*?(?:'''|$)|"(?:\\.|[^"\\])*"?|'(?:\\.|[^'\\])*'?))|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][\w]*)|([\s\S])/g
      : /(\/\/.*$)|("(?:\\.|[^"\\])*"?|'(?:\\.|[^'\\])*'?|`(?:\\.|[^`\\])*`?)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_$][\w$]*)|([\s\S])/g;
    var out = [], m;
    function push(type, text) {
      var last = out[out.length - 1];
      if (last && last[0] === type) last[1] += text; else out.push([type, text]);
    }
    while ((m = re.exec(line)) !== null) {
      if (m[1]) push("com", m[1]);
      else if (m[2]) push("str", m[2]);
      else if (m[3]) push("num", m[3]);
      else if (m[4]) {
        var w = m[4], next = line.slice(re.lastIndex).match(/^\s*\(/);
        push(sets.ctl[w] ? "ctl" : sets.kw[w] ? "kw" : sets.type[w] ? "type" : next ? "fn" : null, w);
      } else push(null, m[5]);
    }
    return out;
  }

  var rules = { LETTERS: LETTERS, tokenize: tokenize, MAX_TRIES: MAX_TRIES, CODE_MULTIPLIER: CODE_MULTIPLIER, MAX_PER_ISSUE: MAX_PER_ISSUE,
    rollBug: rollBug, modesFor: modesFor, reportOptions: reportOptions, challengeFor: challengeFor, points: points,
    newEncounter: newEncounter, choose: choose, answer: answer, batchTitles: batchTitles, recordUrl: recordUrl };
  if (typeof module !== "undefined" && module.exports) { module.exports = rules; return; }

  // ---------------------------------------------------------------- browser UI
  var doc = root.document;
  var $ = function (id) { return doc.getElementById(id); };
  var reduceMotion = root.matchMedia && root.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var DATA, CH, enc;
  var KEY = "bughunt.v2";
  var VERSION = "4.2"; // bump together with game.js?v= in index.html on every release

  function blank() { return { counts: {}, points: 0, catches: 0, pending: [], undo: null }; }
  function load() {
    try {
      var s = JSON.parse(root.localStorage.getItem(KEY));
      if (!s) return blank();
      s.pending = s.pending || []; s.undo = s.undo || null;
      return s;
    } catch (e) { return blank(); }
  }
  function save(s) { try { root.localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* private mode */ } }
  var me = load();

  // Saved progress can outlive the data (a renamed bug) or get damaged. Keep only what the
  // current bug list understands, so one bad entry can never break the page.
  function clean(s) {
    var known = {}; DATA.bugs.forEach(function (b) { known[b.id] = b; });
    var ok = function (c) { return c && known[c.bug] && (c.mode === "report" || c.mode === "code"); };
    var out = blank();
    Object.keys((s && typeof s.counts === "object" && s.counts) || {}).forEach(function (id) {
      var n = Math.floor(Number(s.counts[id]));
      if (known[id] && n > 0) out.counts[id] = n;
    });
    out.catches = Math.max(0, Math.floor(Number(s && s.catches)) || 0);
    out.points = Math.max(0, Math.floor(Number(s && s.points)) || 0);
    out.pending = (Array.isArray(s && s.pending) ? s.pending : []).filter(ok);
    out.undo = Array.isArray(s && s.undo) ? s.undo.filter(ok) : null;
    if (out.undo && !out.undo.length) out.undo = null;
    save(out);
    return out;
  }

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
  function byId(id) { return DATA.bugs.filter(function (b) { return b.id === id; })[0]; }
  function rarity(b) { return DATA.rarities[b.rarity]; }
  function art(id, theme) { return "art/" + id + "-" + theme + ".svg"; }
  function pic(id, alt, cls) {
    var dark = root.matchMedia && root.matchMedia("(prefers-color-scheme: dark)").matches;
    return el("img", { src: art(id, dark ? "dark" : "light"), alt: alt, class: cls || "" });
  }
  function pts(n) { return n + (n === 1 ? " pt" : " pts"); }

  // ---------------------------------------------------------------- Bugdex + leaderboard queue
  function renderDex() {
    var grid = $("dex"); grid.textContent = "";
    var found = 0;
    DATA.bugs.forEach(function (b) {
      var n = me.counts[b.id] || 0;
      if (n) found++;
      grid.appendChild(el("div", { class: "tile" + (n ? "" : " locked"), title: n ? b.name + " · " + rarity(b).label : "Undiscovered " + rarity(b).label + " bug" }, [
        n ? pic(b.id, b.name) : pic("unknown-" + b.rarity, "Undiscovered " + rarity(b).label + " bug"),
        el("div", { class: "tname", text: n ? b.name : "???" }),
        el("div", { class: "tmeta", text: rarity(b).label + (n ? " · ×" + n : "") })
      ]));
    });
    $("stat-found").textContent = found + "/" + DATA.bugs.length;
    $("stat-caught").textContent = me.catches;
    $("stat-points").textContent = me.points;
    renderQueue();
  }

  function renderQueue() {
    var box = $("queue"); box.textContent = "";
    if (me.pending.length) {
      var total = me.pending.reduce(function (s, c) { return s + points(DATA, byId(c.bug), c.mode); }, 0);
      var next = batchTitles(me.pending)[0];
      box.appendChild(el("p", {}, [el("b", { text: me.pending.length + (me.pending.length === 1 ? " catch" : " catches") }),
        " (" + pts(total) + ") not on the leaderboard yet."]));
      box.appendChild(el("button", { class: "send", title: "Opens a pre-filled GitHub issue. Press Create and the bot records them.", onclick: sendBatch },
        [next.count < me.pending.length ? "Add the next " + next.count + " to the leaderboard ↗" : "Add to the leaderboard ↗"]));
    }
    if (me.undo) { // shown after every send, even while more catches are still waiting
      box.appendChild(el("p", { class: "muted small undo" }, ["Sent " + me.undo.length + " to GitHub. Didn't press Create? ",
        el("button", { class: "linkbtn", onclick: undoSend, text: "Put them back" })]));
    }
    fitDex();
  }

  // Make the Bugdex tiles as big as the window allows: measure the free space under the
  // panel and spread it over the 4 rows (capped by the column width). Re-runs on resize
  // and whenever the "Add to the leaderboard" row appears or goes.
  var PAGE_BOTTOM = 16;
  function fitDex() {
    var dex = $("dex"), aside = dex && dex.parentNode, tile = dex && dex.querySelector(".tile");
    if (!tile) return;
    if (root.innerWidth <= 900) { dex.style.removeProperty("--tile"); return; }
    var base = 48;
    dex.style.setProperty("--tile", base + "px");
    var box = aside.getBoundingClientRect();
    var free = root.innerHeight - PAGE_BOTTOM - (box.top + root.scrollY) - box.height;
    var size = base + Math.floor(free / 4);
    size = Math.max(base, Math.min(size, tile.clientWidth, 132));
    dex.style.setProperty("--tile", size + "px");
  }
  // Re-measure on anything that changes the space: a resize, a zoom change, or the window
  // moving to a screen with different display scaling (e.g. laptop <-> external monitor).
  var lastSize = "", settle = null;
  function fitIfChanged() {
    var size = root.innerWidth + "x" + root.innerHeight + "@" + root.devicePixelRatio;
    if (!DATA || size === lastSize) return;
    lastSize = size; fitDex();
  }
  // Check now, and once more after the size settles (a window can change width and height
  // in separate steps, e.g. when it's dragged to another screen).
  function refit() {
    fitIfChanged();
    clearTimeout(settle);
    settle = setTimeout(fitIfChanged, 250);
  }
  root.addEventListener("resize", refit);
  root.addEventListener("load", refit);
  if (root.ResizeObserver) new root.ResizeObserver(refit).observe(doc.documentElement);
  (function watchScaling() {
    if (!root.matchMedia) return;
    var mq = root.matchMedia("(resolution: " + root.devicePixelRatio + "dppx)");
    var onChange = function () { refit(); watchScaling(); };
    if (mq.addEventListener) mq.addEventListener("change", onChange, { once: true });
  })();

  function sendBatch() {
    var next = batchTitles(me.pending)[0];
    if (!next) return;
    root.open(recordUrl(next.title), "_blank", "noopener");
    me.undo = me.pending.slice(0, next.count);
    me.pending = me.pending.slice(next.count);
    save(me); renderQueue();
  }

  function undoSend() {
    if (!me.undo) return;
    me.pending = me.undo.concat(me.pending);
    me.undo = null;
    save(me); renderQueue();
  }

  // ---------------------------------------------------------------- stage
  function setStage(node) { var s = $("stage"); s.textContent = ""; s.appendChild(node); s.scrollTop = 0; }

  function idle() {
    setStage(el("div", { class: "idle" }, [
      el("p", { class: "kicker", text: "Luck finds the bug · skill catches it" }),
      el("button", { class: "catch", onclick: roll }, [el("span", { class: "net", "aria-hidden": "true", text: "🪲" }), "Catch a bug"]),
      el("p", { class: "muted", text: "Commons are everywhere. Legendaries almost never show up." }),
      el("p", { class: "muted small", text: "Every bug has two challenges: a bug report for normal points, or the code for double. You pick." })
    ]));
  }

  function roll() {
    enc = newEncounter(DATA, CH, Math.random);
    var slot = el("div", { class: "slot", "aria-live": "polite" }, [el("span", { class: "slotword", text: "Rolling…" })]);
    setStage(el("div", { class: "rolling" }, [el("p", { class: "kicker", text: "Something is moving in the code…" }), slot]));
    var i = 0, ticks = reduceMotion ? 1 : 14;
    (function tick() {
      var key = i < ticks - 1 ? RARITY_ORDER[i % RARITY_ORDER.length] : enc.bug.rarity;
      var r = DATA.rarities[key];
      slot.firstChild.textContent = r.label;
      slot.style.setProperty("--c", r.color);
      i++;
      if (i < ticks) setTimeout(tick, 60 + i * 12);
      else setTimeout(showChoice, reduceMotion ? 0 : 450);
    })();
  }

  function encHead(sub, locked) {
    var r = rarity(enc.bug);
    return el("div", { class: "enc-head" }, [
      pic("unknown-" + enc.bug.rarity, "An undiscovered " + r.label + " bug", "mystery"),
      el("div", {}, [
        el("p", { class: "kicker", text: "A wild bug appeared" }),
        el("h2", {}, [el("span", { class: "rar", style: "--c:" + r.color, text: r.label }), " bug"]),
        el("p", { class: "muted small" }, [sub, locked ? el("span", { class: "lock", text: "🔒 locked in" }) : null])
      ]),
      enc.mode ? triesDots() : null
    ]);
  }

  function coloured(line, lang) {
    if (!line) return el("code", { text: " " });
    return el("code", {}, tokenize(line, lang).map(function (t) {
      return t[0] ? el("span", { class: "t-" + t[0], text: t[1] }) : t[1];
    }));
  }

  function ticket(text) {
    return el("div", { class: "ticket" }, [
      el("div", { class: "ticket-head" }, [el("span", {}, [el("b", { text: "BUG REPORT" })]), el("span", { text: "status: open" })]),
      el("div", { class: "ticket-body", text: text })
    ]);
  }

  function codeBlock(ch, clickable) {
    return el("div", { class: "code" + (clickable ? "" : " preview"), role: "list" }, ch.lines.map(function (line, i) {
      var kids = [el("span", { class: "ln", text: String(i + 1) }), coloured(line, ch.lang)];
      return clickable
        ? el("button", { class: "line", role: "listitem", onclick: function (e) { pick(i + 1, e.currentTarget); } }, kids)
        : el("div", { class: "line", role: "listitem" }, kids);
    }));
  }

  // One toggle, two challenges: flip between them to read each, then start the one showing.
  function showChoice() {
    var hasReport = enc.modes.indexOf("report") !== -1;
    var current = hasReport ? "report" : "code";
    var panel = el("div", { id: "offer-panel", role: "tabpanel" });
    var go = el("button", { class: "catch small", onclick: function () { start(current); } });
    var tabs = {};

    function tab(mode, label, worth) {
      var disabled = enc.modes.indexOf(mode) === -1;
      tabs[mode] = el("button", { class: "tab", role: "tab", "aria-controls": "offer-panel",
        onclick: function () { if (!disabled) show(mode); } },
        [label, el("small", { text: disabled ? "code only" : worth })]);
      if (disabled) { tabs[mode].disabled = true; tabs[mode].title = "A Legendary is code only"; }
      return tabs[mode];
    }

    function show(mode) {
      current = mode;
      Object.keys(tabs).forEach(function (m) {
        tabs[m].classList.toggle("on", m === mode);
        tabs[m].setAttribute("aria-selected", m === mode ? "true" : "false");
      });
      panel.textContent = "";
      if (mode === "report") {
        panel.appendChild(ticket(enc.offers.report.text));
        panel.appendChild(el("p", { class: "muted small panel-note", text: "You'll name the bug from 4 options of the same rarity." }));
      } else {
        panel.appendChild(codeBlock(enc.offers.code, false));
        panel.appendChild(el("p", { class: "muted small panel-note", text: "You'll click the broken line · " + (enc.offers.code.lang === "python" ? "Python" : "JavaScript") }));
      }
      if (!hasReport) panel.appendChild(el("p", { class: "muted small", text: "A Legendary is the only bug of its rarity, so a bug report would give it away. This one is code only." }));
      go.textContent = mode === "report" ? "Solve the report →" : "Find the line →";
    }

    var rp = points(DATA, enc.bug, "report"), cp = points(DATA, enc.bug, "code");
    var toggle = el("div", { class: "toggle", role: "tablist", "aria-label": "Choose a challenge" }, [
      tab("report", "Bug report", pts(rp)),
      tab("code", "Code", pts(cp) + " (double)")
    ]);
    show(current);
    setStage(el("div", { class: "choice" }, [
      encHead("Pick a challenge. Flip between them to read both. You get 3 tries."),
      toggle, panel,
      el("div", { class: "choice-go" }, [go, el("span", { class: "muted small", text: "🔒 Your choice locks once you start." })])
    ]));
  }

  function start(mode) {
    if (!choose(enc, mode)) return;
    var ch = enc.challenge;
    var body;
    if (mode === "report") {
      body = el("div", {}, [
        ticket(ch.text),
        el("p", { class: "q", text: "Which bug did this?" }),
        el("div", { class: "opts" }, enc.options.map(function (id, i) {
          return el("button", { class: "opt", onclick: function (e) { pick(i, e.currentTarget); } },
            [el("b", { text: LETTERS[i] }), byId(id).name]);
        }))
      ]);
    } else {
      body = el("div", {}, [
        el("p", { class: "q", text: "Which line has the bug? Click it." }),
        codeBlock(ch, true),
        el("p", { class: "muted small", text: ch.lang === "python" ? "Python" : "JavaScript" })
      ]);
    }
    var sub = mode === "code" ? "Code · " + pts(points(DATA, enc.bug, "code")) + " (double)" : "Bug report · " + pts(points(DATA, enc.bug, "report"));
    setStage(el("div", { class: "challenge" }, [encHead(sub, true), body, el("p", { id: "feedback", class: "feedback", "aria-live": "polite" })]));
  }

  function triesDots() {
    var d = el("span", { class: "tries", "aria-label": (MAX_TRIES - enc.tries) + " tries left" });
    for (var i = 0; i < MAX_TRIES; i++) d.appendChild(el("i", { class: i < MAX_TRIES - enc.tries ? "on" : "" }));
    return d;
  }

  function pick(value, button) {
    var res = answer(enc, DATA, value);
    if (res.status === "caught") return caught(res);
    if (res.status === "escaped") return escaped();
    if (res.status !== "wrong") return;
    button.disabled = true;
    button.classList.add("nope");
    var fb = $("feedback");
    fb.textContent = "Not that one. Hint: " + enc.challenge.hint + " (" + res.triesLeft + " " + (res.triesLeft === 1 ? "try" : "tries") + " left)";
    fb.classList.remove("shake"); void fb.offsetWidth; fb.classList.add("shake");
    var dots = doc.querySelector(".tries");
    dots.parentNode.replaceChild(triesDots(), dots);
  }

  function caught(res) {
    var b = enc.bug, r = rarity(b);
    var first = !me.counts[b.id];
    me.counts[b.id] = (me.counts[b.id] || 0) + 1;
    me.catches += 1; me.points += res.points;
    me.pending.push({ bug: b.id, mode: enc.mode });
    me.undo = null;
    save(me); renderDex();
    setStage(el("div", { class: "result" }, [
      pic(b.id, b.name, "caught-art"),
      el("div", {}, [
        el("p", { class: "kicker", text: first ? "New in your Bugdex!" : "Caught again" }),
        el("h2", { text: b.name }),
        el("p", {}, [el("span", { class: "rar", style: "--c:" + r.color, text: r.label }), " · +" + pts(res.points) + (enc.mode === "code" ? " (double for code)" : "")]),
        el("p", {}, [el("b", { text: "Why: " }), enc.challenge.explain]),
        el("p", { class: "flavor", text: b.flavor }),
        el("div", { class: "actions" }, [
          el("button", { class: "catch small", onclick: roll, text: "Catch another" }),
          el("span", { class: "muted small", text: "Added to your queue. Send it to the leaderboard from the Bugdex panel." })
        ])
      ])
    ]));
  }

  function escaped() {
    var good = enc.mode === "report" ? enc.bug.name : "line " + enc.challenge.answer.join(" or ");
    setStage(el("div", { class: "idle" }, [
      el("p", { class: "kicker", text: "💨 The bug escaped" }),
      el("p", {}, ["It was ", el("b", { text: good }), ". " + enc.challenge.explain]),
      el("button", { class: "catch", onclick: roll, text: "Catch another" })
    ]));
  }

  function boot() {
    // ?v= changes with each release, so a browser never mixes a cached old file with new ones.
    Promise.all([fetch("data/bugs.json?v=" + VERSION).then(function (r) { return r.json(); }),
                 fetch("data/challenges.json?v=" + VERSION).then(function (r) { return r.json(); })])
      .then(function (res) {
        DATA = res[0]; CH = res[1];
        me = clean(me);
        renderDex(); idle();
        if (doc.fonts && doc.fonts.ready) doc.fonts.ready.then(fitDex);
        $("reset").addEventListener("click", function () {
          if (root.confirm("Clear your Bugdex, score and unsent catches on this device?")) { me = blank(); save(me); renderDex(); }
        });
      })
      .catch(function () { setStage(el("p", { text: "The bugs failed to load. Try refreshing the page." })); });
  }
  doc.addEventListener("DOMContentLoaded", boot);
})(typeof window !== "undefined" ? window : globalThis);
