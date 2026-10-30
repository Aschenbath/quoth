"use strict";

const MODEL_ORDER = ["gemma-3-1b-pt", "OLMo-2-0425-1B", "gemma-4-E2B", "gemma-4-E4B"]; // smallest to largest
const STAR = "gemma-4-E4B";
const OLMO = "OLMo-2-0425-1B";
const TIERS = [
  ["canon", "The canon"],
  ["genre", "Genre favourites"],
  ["forgotten", "The forgotten"],
  ["late", "Posted after training"],
  ["novel", "New control text"],
];
const KINDS = [
  ["opening", "Openings", "var(--marigold)"],
  ["quoted", "Quoted lines", "var(--teal)"],
  ["body", "Random pages", "var(--stone)"],
  ["novel", "New control text", "var(--ink-2)"],
];
const WEB_NAMES = { dclm: "the open web (DCLM)", "olmo-mix": "OLMo 2's training data" };
const BIOS = {
  72421: "Best known for the Mapp and Lucia novels; he also wrote dozens of ghost stories.",
  1617: "New England writer, best known for A New England Nun.",
  4514: "The first woman to win the Pulitzer Prize for Fiction, for The Age of Innocence.",
  9956: "Pen name of Violet Paget, who wrote on art and aesthetics.",
  10052: "Scottish novelist who wrote more than ninety novels.",
  59165: "Novelist and critic who first applied the phrase “stream of consciousness” to fiction.",
  8602: "Irish-born novelist of the City of London, its business and its haunted houses.",
  69297: "Welsh-born novelist once called the queen of the circulating libraries.",
  37707: "Novelist, travel writer and Egyptologist; she co-founded the Egypt Exploration Fund.",
  78060: "English hymn writer and novelist.",
  76737: "American journalist and writer.",
  76950: "Novelist, actress and spiritualist; daughter of the sea novelist Captain Marryat.",
  77782: "Prolific writer of historical and supernatural fiction.",
  78605: "Novelist, suffragist and literary hostess.",
  78162: "English novelist, who also wrote Dartmoor novels as John Trevena.",
};

let D;
const state = { model: STAR, pg: 43 };
const $ = (s, root = document) => root.querySelector(s);

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else e.setAttribute(k, v);
  }
  for (const k of kids) if (k != null && k !== false) e.append(k);
  return e;
}
const svgEl = (tag, attrs) => {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  return e;
};
const fmt = (n) => n.toLocaleString("en-US");
const pct = (x) => `${Math.round(x * 100)}%`;
const name = (m) => (D.models.find((x) => x.id === m) || { name: m }).name;
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

fetch("data.json")
  .then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  })
  .then((d) => {
    D = d;
    D.models.sort((a, b) => MODEL_ORDER.indexOf(a.id) - MODEL_ORDER.indexOf(b.id));
    D.workByPg = new Map(D.works.map((w) => [w.pg, w]));
    for (const w of D.works) for (const id of w.passages) D.passages[id].work = w;
    init();
  }, (e) => {
    $("#rec-text").textContent = "Could not load data.json (" + e + ").";
  });

function init() {
  for (const n of document.querySelectorAll('[data-n="passages"]')) n.textContent = fmt(Object.keys(D.passages).length);
  drawAll([renderStats, renderRecital, renderRaven, renderOpenings, renderModelButtons, renderWorks, renderBook, renderKinds,
    renderTiers, renderScale, renderWeb, renderAltar, renderMethodNumbers]);
  // Charts are drawn at their shown width, so redraw them when the width really changes.
  let shownW = innerWidth, timer = null;
  addEventListener("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (Math.abs(innerWidth - shownW) < 24) return;
      shownW = innerWidth;
      drawAll([renderKinds, renderTiers, renderScale, renderWeb]);
    }, 200);
  });
}

function drawAll(draws) {
  // Each section draws independently, so one failure leaves the rest of the page readable.
  for (const draw of draws) {
    try { draw(); } catch (e) { console.error(draw.name, e); }
  }
}

/* ---------------- words ---------------- */

function wordClass(sc, wi) {
  if (!sc) return "w";
  if (wi < sc.g) return "w run";
  // When the run ends on a paragraph break rather than inside a word, the next
  // word itself was still predicted, so it is not marked as the mistake.
  if (wi === sc.g && sc.h[wi] === "0") return "w break";
  return sc.h[wi] === "1" ? "w hit" : "w miss";
}

function passageText(p, sc, opts = {}) {
  const box = el("div", { class: "text verse" });
  box.append(el("span", { class: "prefix", text: p.prefix }));
  if (p.sep.includes("\n")) box.append(p.sep.replace(/ /g, ""));
  const spans = [];
  let wi = 0;
  p.target.forEach((s, i) => {
    if (i % 2) { box.append(s); return; }
    const span = el("span", { class: opts.hidden ? "w wait" : wordClass(sc, wi), text: s });
    spans.push(span);
    box.append(span);
    wi++;
  });
  return { box, spans };
}

const targetWords = (p) => p.target.filter((_, i) => i % 2 === 0);

/* ---------------- hero ---------------- */

function renderStats() {
  const s = D.summary[STAR];
  const recited = s.recited.length;
  const forgottenRecited = Object.values(D.summary).reduce((n, m) =>
    n + m.recited.filter((r) => ["forgotten", "late"].includes(D.passages[r.id].work.tier)).length, 0);
  const q = (t) => D.works.filter((w) => w.tier === t).reduce((n, w) => n + w.quoted, 0);
  const tiles = [
    [fmt(D.raven.words), `words of The Raven ${name(STAR)} writes on its own, from the poem's first 40`],
    [String(recited), `passages of ${fmt(Object.keys(D.passages).length)} it recites for ten exact words or more`],
    [String(forgottenRecited), "passages recited from the 15 forgotten or newly posted books, by any of the four models"],
    [`${q("forgotten")} vs ${q("canon")}`, "Wikiquote lines found in the 9 forgotten books vs the 10 classics"],
  ];
  $("#stats").replaceChildren(...tiles.map(([v, l]) => el("div", { class: "stat" }, el("div", { class: "v", text: v }), el("div", { class: "l", text: l }))));
}

let recitalTimer = null;
function renderRecital(which = "opening") {
  const picks = {
    opening: ["pg43-00", "the opening"],
    quoted: ["pg43-q04", "a line people quote"],
    body: ["pg43-15", "a page from the middle"],
  };
  const [pid, label] = picks[which];
  const p = D.passages[pid];
  const sc = p.scores[STAR];
  $("#rec-where").textContent = which === "opening" ? label : `${label}, ${pct(p.pos)} of the way in`;
  const { box, spans } = passageText(p, sc, { hidden: !reduced });
  $("#rec-text").className = "text verse";
  $("#rec-text").replaceChildren(...box.childNodes);
  $("#rec-verdict").textContent = "";
  clearTimeout(recitalTimer);

  const words = targetWords(p);
  const novel = D.summary[STAR].kinds.novel.top1;
  const verdict = () => {
    const v = $("#rec-verdict");
    v.replaceChildren();
    if (which === "opening") {
      v.append(`Given the first 40 words and nothing else, ${name(STAR)} continues for `,
        el("strong", { text: `${sc.g} words` }), " exactly as Stevenson wrote them.");
      if (p.said) {
        const said = p.said.trim().split(/\s+/);
        if (said[sc.g] && said[sc.g] !== words[sc.g]) v.append(` Then it wrote “${said[sc.g]}” where he wrote “${words[sc.g]}”.`);
      }
    } else if (which === "quoted") {
      v.append("Deep in the book, the line people quote. Given the 40 words before it, ",
        sc.g === words.length ? el("strong", { text: `it recites the whole line` }) : el("strong", { text: `it recites ${sc.g} of its ${words.length} words` }), ".");
    } else {
      const pages = p.work.passages.map((id) => D.passages[id]).filter((q) => q.kind === "body");
      const avg = pages.reduce((s, q) => s + q.scores[STAR].t, 0) / pages.length;
      v.append("A page from the middle of the same book: it predicts ", el("strong", { text: pct(sc.t) }),
        ` of the words and recites ${sc.g === 0 ? "none" : sc.g === 1 ? "one" : sc.g} of them. The book's ${pages.length} random pages average ${pct(avg)}; passages new control text, which it cannot have seen, ${pct(novel)}.`);
    }
  };
  if (reduced) { verdict(); }
  else {
    let i = 0;
    const step = () => {
      if (i >= spans.length) { verdict(); return; }
      spans[i].className = wordClass(sc, i);
      const delay = i < sc.g ? 85 : 35;
      i++;
      recitalTimer = setTimeout(step, delay);
    };
    recitalTimer = setTimeout(step, 600);
  }
  const sw = $("#rec-switch");
  sw.replaceChildren(...Object.entries({ opening: "The opening", quoted: "A quoted line", body: "A random page" }).map(([k, t]) => {
    const b = el("button", { class: "btn", type: "button", "aria-pressed": String(k === which), text: t });
    b.addEventListener("click", () => renderRecital(k));
    return b;
  }));
}

/* ---------------- the Raven ---------------- */

/* The long generation cut into stanzas of [kind, text], with the words that differ from the 1845 text marked. */
function ravenStanzas(r) {
  const stanzas = [[]];
  const push = (kind, text) => text.split(/(\n[ \t]*\n\s*)/).forEach((part, i) => {
    if (i % 2) stanzas.push([]);
    else if (part) stanzas[stanzas.length - 1].push([kind, part]);
  });
  let at = 0;
  for (const [kind, text] of r.marked) {
    let from = 0;
    for (const s of r.passed) {
      const i = s.at - at;
      if (i < from || i >= text.length) continue;
      push(kind, text.slice(from, i));
      push("slip", text.slice(i, i + s.said.length));
      from = i + s.said.length;
    }
    push(kind, text.slice(from));
    at += text.length;
  }
  return stanzas;
}

function stanzaEl(parts, r) {
  const box = el("p", { class: "stanza" });
  for (const [kind, text] of parts) {
    if (kind === "slip") {
      const s = r.passed.find((x) => x.said === text);
      box.append(el("span", { class: "slip", title: `the 1845 text has “${s.book}”`, text }));
    } else {
      box.append(el("span", { class: kind === "book" ? "w run" : "own", text }));
    }
  }
  return box;
}

function renderRaven() {
  const r = D.raven, p = D.passages["pg1065-00"], sc = p.scores[STAR];
  const stanzas = ravenStanzas(r);
  const loop = stanzas.pop().map(([, t]) => t).join("");
  const line = loop.slice(0, loop.indexOf("!") + 1);
  const times = loop.split(line).length - 1;
  for (const n of document.querySelectorAll('[data-n="star"]')) n.textContent = name(STAR);
  for (const n of document.querySelectorAll('[data-n="raven-words"]')) n.textContent = fmt(r.words);

  const gap = (from, to, label) => {
    const b = el("button", { class: "btn gap", type: "button", text: label });
    b.addEventListener("click", () => b.replaceWith(...stanzas.slice(from, to).map((s) => stanzaEl(s, r))));
    return b;
  };
  const first = stanzaEl(stanzas[0], r);
  first.prepend(el("span", { class: "prefix", text: p.prefix }));
  $("#raven-poem").replaceChildren(first, gap(1, 10, "Stanzas 2 to 10, all from memory: show them"),
    stanzaEl(stanzas[10], r), gap(11, 12, "Stanza 12, from memory: show it"), stanzaEl(stanzas[12], r),
    el("p", { class: "stanza" }, el("span", { class: "own", text: line }), el("span", { class: "times", text: ` and ${fmt(times - 1)} more times, until the 2,000 tokens I allowed ran out` })));

  const stops = el("div", { class: "fork" },
    el("p", {}, el("span", { class: "lbl", text: "Where Poe goes on" }),
      "On the cushion’s velvet lining that the lamp-light gloated o’er,\nBut whose velvet-violet lining with the lamp-light gloating o’er,\nShe shall press, ah, nevermore!"));
  const nums = [
    ["40", "words given"],
    [fmt(r.words), "words that follow, from memory"],
    [String(r.passed.length), "of them differ from the 1845 text"],
    [String(sc.g), "words is its exact score in the main test"],
  ];
  $("#raven-notes").replaceChildren(el("div", { class: "tally" }, ...nums.map(([v, l]) => el("div", {}, el("b", { text: v }), el("span", { text: l })))), stops);

  const raven = D.workByPg.get(1065).passages.map((id) => D.passages[id]);
  const q3 = D.passages["pg1065-q03"].recall.pieces.at(-1);
  const low = Math.min(...raven.map((q) => q.scores[STAR].t));
  $("#raven-after").textContent = `It stops two lines short of “She shall press, ah, nevermore!” and writes lines of its own. Then it does what the bird does, ` +
    `and says one thing over and over. Poe never wrote “${line}” It does not stop because it knows no more. Started from a line in the eighth stanza, ` +
    `it jumps ahead and recites ${fmt(q3.words)} words from stanza ${q3.blocks[0]} into stanza ${q3.blocks[1]}, where the 400 tokens I allowed ran out. All ${raven.length} sampled passages of The Raven are ` +
    `at least ${pct(Math.floor(low * 100) / 100)} predicted.`;
  $("#raven-floor").textContent = `The main test on this page gives that same passage a score of ${sc.g} words. It compares exactly, and the third word is a ` +
    `quotation mark this copy prints straight and the model writes curly. Project Gutenberg's copy of the poem is also a different printing, with “visiter” ` +
    `for “visitor” and “sad soul” for “fancy”, so I checked the recitation against the Poetry Foundation's text of the 1845 edition as well. Everything ` +
    `below uses the strict test, so read its counts as a floor.`;
}

function renderOpenings() {
  const fig = $("#fig-openings");
  figHead(fig, "Every opening, read the same way", `${name(STAR)} was given each book's first 40 words and left to write. The bars count the words that follow from memory; the last column is the main test's share of the next 50 words, predicted one at a time with each mistake corrected.`);
  const rows = D.works.filter((w) => w.pg).map((w) => {
    const p = D.passages[`pg${w.pg}-00`];
    return { w, p, n: p.recall ? p.recall.words : 0, t: p.scores[STAR].t };
  });
  const max = Math.max(...rows.map((r) => r.n));
  const row = ({ w, n, t }) => el("div", { class: "opn" },
    el("span", { class: "t", text: w.title, title: `${w.author}, ${w.year} · downloaded ${fmt(w.downloads)} times in the 30 days to Oct 30, 2026` }),
    el("span", { class: "bar" }, n ? el("i", { style: `width:${Math.max(0.4, n / max * 100)}%` }) : null),
    el("span", { class: "n", text: fmt(n) }),
    el("span", { class: "p", text: pct(t) }));
  const group = (tier, label) => el("div", { class: "opn-group" },
    el("div", { class: "opn head" }, el("h4", { text: label }), el("span"), el("span", { class: "n", text: "words" }), el("span", { class: "p", text: "predicted" })),
    ...rows.filter((r) => r.w.tier === tier).sort((a, b) => b.n - a.n || b.t - a.t).map(row));
  fig.append(el("div", { class: "opns" },
    el("div", {}, group("canon", "The canon"), group("genre", "Genre favourites")),
    el("div", {}, group("forgotten", "The forgotten"), group("late", "Posted after training"))));
  const frank = rows.find((r) => r.w.pg === 84), raven = rows.find((r) => r.w.pg === 1065);
  fig.append(el("figcaption", { text: `Words are compared without punctuation or case, and a slip of a word or two is passed over if the next three words line up again. Each opening had 400 tokens of room, The Raven 2,000 because it had not stopped. One wrong turn is usually the end: ${frank.w.title}, downloaded ${fmt(frank.w.downloads)} times in the 30 days to Oct 30, 2026 to The Raven's ${fmt(raven.w.downloads)}, is ${pct(frank.t)} predicted when corrected, but left alone it goes wrong after ${plural(frank.n, "word")} and does not find its way back.` }));
}

/* ---------------- reader ---------------- */

function renderModelButtons() {
  $("#model-btns").replaceChildren(...D.models.map((m) => {
    const b = el("button", { class: "btn", type: "button", "aria-pressed": String(m.id === state.model), text: m.name });
    b.addEventListener("click", () => {
      state.model = m.id;
      renderModelButtons();
      renderWorks();
      renderBook();
    });
    return b;
  }));
}

function bestRun(w, m) {
  return Math.max(0, ...w.passages.map((id) => (D.passages[id].scores[m] || { g: 0 }).g));
}

function renderWorks() {
  const nav = $("#works");
  const kids = [];
  for (const [tier, label] of TIERS) {
    kids.push(el("h4", { text: label }));
    for (const w of D.works.filter((x) => x.tier === tier)) {
      const best = bestRun(w, state.model);
      const b = el("button", { class: "work", type: "button", "aria-current": String(w.pg === state.pg) },
        el("span", { text: w.title }),
        el("small", { text: w.pg ? `${w.author}, ${w.year}` : "16 passages, written for this project" }),
        el("span", { class: "best" + (best >= D.recited_at ? " lit" : ""), text: best >= D.recited_at ? String(best) : "–",
          title: `longest recited run: ${best} words` }));
      b.addEventListener("click", () => {
        state.pg = w.pg;
        renderWorks();
        renderBook();
        if (matchMedia("(max-width: 900px)").matches) $("#book").focus({ preventScroll: true });
      });
      kids.push(b);
    }
  }
  nav.replaceChildren(...kids);
  const cur = nav.querySelector('[aria-current="true"]');
  if (cur && matchMedia("(max-width: 900px)").matches) cur.scrollIntoView({ block: "nearest", inline: "nearest" });
}

function webLine(p) {
  if (!p.web) return null;
  const parts = Object.entries(p.web).map(([k, n]) => `${WEB_NAMES[k] || k}: ${fmt(n)}`);
  return el("span", { text: "Copies of this transition in " + parts.join(" · "), title: "how often the last 5 given words followed by the first 5 target words occur, counted with infini-gram" });
}

function card(p) {
  const sc = p.scores[state.model];
  const where = p.kind === "opening" ? "Opening" : p.kind === "novel" ? "Control passage" :
    `${p.kind === "quoted" ? "Quoted line" : "Page"} · ${pct(p.pos)} of the way in`;
  const right = !sc ? "not scored" : sc.g >= D.recited_at ? el("span", { class: "recited", text: `recited ${sc.g} words` }) :
    `predicted ${pct(sc.t)} · longest run ${sc.g} word${sc.g === 1 ? "" : "s"}`;
  const c = el("article", { class: "card" }, el("div", { class: "head" }, el("b", { text: where }), el("span", {}, right)));
  c.append(passageText(p, sc).box);

  if (p.said && state.model === STAR) {
    const words = targetWords(p);
    const said = p.said.trim().split(/\s+/);
    let n = 0;
    while (n < said.length && n < words.length && said[n] === words[n]) n++;
    if (n < said.length) {
      const box = el("div", { class: "said" }, el("span", { class: "lbl", text: `What ${name(STAR)} wrote on its own` }));
      if (n) box.append(el("span", { class: "same", text: said.slice(0, n).join(" ") + " " }));
      box.append(el("span", { class: "own", text: said.slice(n).join(" ") }));
      if (sc && n !== sc.g) {
        box.append(el("span", { class: "lbl note", text: `Generating freely it kept to the text for ${n} word${n === 1 ? "" : "s"}; the token-by-token score above counts ${sc.g}.` }));
      }
      c.append(box);
    }
  }
  const foot = el("div", { class: "foot" }, webLine(p), p.source ? el("span", { text: `Quote found on Wikiquote: ${p.source}` }) : null);
  if (foot.childNodes.length) c.append(foot);
  return c;
}

function renderBook() {
  const w = D.workByPg.get(state.pg);
  const book = $("#book");
  const ps = w.passages.map((id) => ({ id, ...D.passages[id] }));
  const scored = ps.filter((p) => p.scores[state.model]);
  const mean = scored.reduce((s, p) => s + p.scores[state.model].t, 0) / Math.max(1, scored.length);
  const rec = scored.filter((p) => p.scores[state.model].g >= D.recited_at).length;
  const meta = w.pg
    ? `${w.author} (${w.dates}), ${w.year} · downloaded ${fmt(w.downloads)} times in the 30 days to Oct 30, 2026 · on Project Gutenberg since ${w.released.slice(0, 4)}`
    : "Passages in the style of the books, written for this project on 2026-10-30, after every model here was trained.";
  const head = el("div", { class: "book-head" }, el("h3", { text: w.title }), el("div", { class: "meta", text: meta }),
    el("div", { class: "meta", text: `${name(state.model)}: ${rec} of ${scored.length} passages recited · ${pct(mean)} of words predicted on average` }),
    w.pg ? el("div", { class: "meta" }, el("a", { href: `https://www.gutenberg.org/ebooks/${w.pg}`, text: "Read it on Project Gutenberg" })) : null);
  const groups = [
    ["opening", "The opening"],
    ["quoted", "Lines people quote"],
    ["body", "Random pages, first to last"],
    ["novel", "Control passages"],
  ];
  const kids = [head];
  for (const [k, t] of groups) {
    const g = ps.filter((p) => p.kind === k).sort((a, b) => a.pos - b.pos);
    if (!g.length) continue;
    kids.push(el("div", { class: "group-title", text: `${t} (${g.length})` }));
    const first = k === "body" ? g.slice(0, 8) : g;
    for (const p of first) kids.push(card(p));
    if (first.length < g.length) {
      const more = el("button", { class: "btn more", type: "button", text: `Show all ${g.length} pages` });
      more.addEventListener("click", () => {
        const frag = document.createDocumentFragment();
        for (const p of g.slice(first.length)) frag.append(card(p));
        more.replaceWith(frag);
      });
      kids.push(more);
    }
  }
  if (!ps.some((p) => p.kind === "quoted") && w.pg) {
    kids.splice(2, 0, el("p", { class: "meta", text: "Wikiquote has no lines from this book." }));
  }
  book.replaceChildren(...kids);
}

/* ---------------- charts ---------------- */

const tip = () => $("#tip");
function showTip(evt, strong, ...lines) {
  const t = tip();
  t.replaceChildren(el("strong", { text: strong }), ...lines.map((l) => el("div", { text: l })));
  t.classList.add("on");
  const r = evt.target.getBoundingClientRect?.();
  const x = evt.clientX ?? (r ? r.left + r.width / 2 : 0);
  const y = evt.clientY ?? (r ? r.top : 0);
  const w = t.offsetWidth, h = t.offsetHeight;
  t.style.left = Math.min(innerWidth - w - 8, Math.max(8, x + 14)) + "px";
  t.style.top = Math.max(8, y - h - 12) + "px";
}
const hideTip = () => tip().classList.remove("on");

function figHead(fig, title, sub) {
  fig.replaceChildren(el("p", { class: "fig-title", text: title }), sub ? el("p", { class: "fig-sub", text: sub }) : null);
}

function tableView(head, rows) {
  const t = el("table", {}, el("thead", {}, el("tr", {}, ...head.map((h) => el("th", { text: h })))),
    el("tbody", {}, ...rows.map((r) => el("tr", {}, ...r.map((c) => el("td", { text: String(c) }))))));
  return el("details", { class: "table" }, el("summary", { text: "Show as a table" }), el("div", { class: "scroll" }, t));
}

// Charts are drawn at the width they are shown at, so their text stays at its CSS size.
// The node must already be in the document.
const widthOf = (node) => Math.max(260, Math.floor(node.getBoundingClientRect().width));
const keyOf = (series) => el("div", { class: "key" }, ...series.map(([label, color]) => el("span", {}, el("i", { style: `background:${color}` }), label)));
const statOf = (c) => ({ mean: c.top1, lo: c.top1_ci[0], hi: c.top1_ci[1], tip: [`${c.n} passages, ${c.recited} recited`] });
const ciText = (c) => `${pct(c.top1_ci[0])}–${pct(c.top1_ci[1])}`;
const domainOf = (marks) => [Math.floor(Math.min(...marks.map((m) => m.lo)) * 10) / 10, Math.ceil(Math.max(...marks.map((m) => m.hi)) * 10) / 10];

function panels(fig, titles) {
  // Every panel goes into the grid before any is measured, so each one already has its column width.
  const grid = el("div", { class: "panels" });
  fig.append(grid);
  return titles.map((t) => {
    const p = el("div", {}, el("div", { class: "panel-title", text: t }));
    grid.append(p);
    return p;
  });
}

function dotRows(svg, rows, x0, dom, opts = {}) {
  // rows: [{label, marks: [{name, mean, lo, hi, color, tip}]}]; two marks in one row are dodged.
  const W = +svg.getAttribute("width"), x1 = W - 18, rowH = opts.rowH || 30, gap = 14;
  const top = opts.ref && opts.ref[1] ? 30 : 10, bottom = 28;
  const X = (v) => x0 + (v - dom[0]) / (dom[1] - dom[0]) * (x1 - x0);
  const H = top + rows.length * rowH + bottom;
  svg.setAttribute("height", H);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const step = (x1 - x0) / ((dom[1] - dom[0]) * 10) >= 46 ? 0.1 : 0.2;
  for (let i = 0; dom[0] + i * step <= dom[1] + 1e-9; i++) {
    const v = dom[0] + i * step;
    svg.append(svgEl("line", { class: "gridline", x1: X(v), x2: X(v), y1: top - 6, y2: H - bottom + 6 }));
    const t = svgEl("text", { class: "tick", x: X(v), y: H - 8, "text-anchor": "middle" });
    t.textContent = pct(v);
    svg.append(t);
  }
  if (opts.ref) {
    const [v, label] = opts.ref;
    svg.append(svgEl("line", { class: "refline", x1: X(v), x2: X(v), y1: top - (label ? 10 : 6), y2: H - bottom + 6 }));
    if (label) {
      const right = X(v) > (x0 + x1) / 2;
      const t = svgEl("text", { class: "reflab", x: X(v) + (right ? -5 : 5), y: top - 12, "text-anchor": right ? "end" : "start" });
      t.textContent = label;
      svg.append(t);
    }
  }
  rows.forEach((r, i) => {
    const yc = top + i * rowH + rowH / 2;
    const lab = svgEl("text", { class: "rowlab", x: x0 - 12, y: yc + 4, "text-anchor": "end" });
    lab.textContent = r.label;
    svg.append(lab);
    const n = r.marks.length, hh = n > 1 ? gap : 24;
    r.marks.forEach((m, j) => {
      const y = yc + (j - (n - 1) / 2) * gap;
      const what = m.name ? `${r.label}, ${m.name.toLowerCase()}` : r.label;
      const g = svgEl("g", { class: "mark" });
      g.append(svgEl("line", { class: "ci", x1: X(m.lo), x2: X(m.hi), y1: y, y2: y, stroke: m.color, opacity: 0.6 }));
      const hit = svgEl("rect", { class: "hit-area", x: X(m.lo) - 12, y: y - hh / 2, width: Math.max(24, X(m.hi) - X(m.lo) + 24), height: hh,
        tabindex: 0, role: "img", "aria-label": `${what}: ${pct(m.mean)} (95% interval ${pct(m.lo)} to ${pct(m.hi)})` });
      g.append(hit, svgEl("circle", { class: "dot", cx: X(m.mean), cy: y, r: 5.5, fill: m.color }));
      const on = (e) => showTip(e, pct(m.mean), what, `95% interval ${pct(m.lo)}–${pct(m.hi)}`, ...(m.tip || []));
      hit.addEventListener("pointermove", on);
      hit.addEventListener("focus", on);
      hit.addEventListener("pointerleave", hideTip);
      hit.addEventListener("blur", hideTip);
      svg.append(g);
    });
  });
}

function renderKinds() {
  const fig = $("#fig-kinds");
  figHead(fig, "The ten classics: openings, quoted lines and random pages",
    "Share of words each model predicts exactly: mean over passages, with 95% bootstrap intervals. The vertical line extends the bottom row, text new control text, which no model can have seen.");
  const cells = [["canon/opening", "Openings", "var(--marigold)"], ["canon/quoted", "Quoted lines", "var(--teal)"],
    ["canon/body", "Random pages", "var(--stone)"], ["novel/novel", "New control text", "var(--ink-2)"]];
  const per = D.models.map((m) => {
    const s = D.summary[m.id];
    return { m, ref: s.cells["novel/novel"], rows: cells.filter(([c]) => s.cells[c]).map(([c, label, color]) => ({ c: s.cells[c], label, color })) };
  });
  const dom = domainOf(per.flatMap((x) => x.rows.map((r) => statOf(r.c))));
  const table = [];
  panels(fig, D.models.map((m) => m.name)).forEach((panel, i) => {
    const { m, ref, rows } = per[i];
    const svg = svgEl("svg", { width: widthOf(panel), class: "chart", role: "group", "aria-label": `${m.name}: share of words predicted in the ten classics, by kind of passage` });
    dotRows(svg, rows.map((r) => ({ label: r.label, marks: [{ ...statOf(r.c), color: r.color }] })), 124, dom, { rowH: 30, ref: ref && [ref.top1] });
    panel.append(svg);
    for (const r of rows) table.push([m.name, r.label, pct(r.c.top1), ciText(r.c), r.c.n, r.c.recited]);
  });
  fig.append(tableView(["model", "passages", "predicted", "95% interval", "n", "recited"], table));
}

function renderTiers() {
  const fig = $("#fig-tiers");
  const s = D.summary[STAR];
  figHead(fig, `${name(STAR)}: openings and random pages, by how famous the book is`, "Openings stand out only in books people still read.");
  const series = [["opening", "Openings", "var(--marigold)"], ["body", "Random pages", "var(--stone)"]];
  fig.append(keyOf(series.map(([, label, color]) => [label, color])));
  const rows = [], table = [];
  for (const [t, label] of TIERS.filter(([t]) => t !== "novel")) {
    const marks = series.filter(([k]) => s.cells[`${t}/${k}`]).map(([k, sl, color]) => {
      const c = s.cells[`${t}/${k}`];
      table.push([label, sl, pct(c.top1), ciText(c), c.n, c.recited]);
      return { name: sl, ...statOf(c), color };
    });
    rows.push({ label, marks });
  }
  const nov = s.cells["novel/novel"];
  table.push(["New control text", "Control passages", pct(nov.top1), ciText(nov), nov.n, nov.recited]);
  const box = el("div");
  fig.append(box);
  const svg = svgEl("svg", { width: widthOf(box), class: "chart", role: "group", "aria-label": `${name(STAR)}: share of words predicted in openings and random pages, by tier` });
  dotRows(svg, rows, 148, domainOf(rows.flatMap((r) => r.marks)), { rowH: 46, ref: [nov.top1, `new control text ${pct(nov.top1)}`] });
  box.append(svg);
  fig.append(tableView(["books", "passages", "predicted", "95% interval", "n", "recited"], table),
    el("figcaption", { text: "The line is the 16 passages written for this project. An AI wrote them, and text written by an AI may be easier for a model to predict, so they may be a generous baseline: random pages from the forgotten books land a little below them, level with the books posted after training." }));
}

function renderScale() {
  const fig = $("#fig-scale");
  figHead(fig, "Passages recited, ten words or more", `Out of ${fmt(Object.keys(D.passages).length)}, smallest model to largest. The larger Gemma 4 recites the most, though the models also differ in data and design.`);
  const box = el("div");
  fig.append(box);
  const W = widthOf(box), rowH = 34, x0 = 112, x1 = W - 44;
  const vals = D.models.map((m) => ({ m, n: D.summary[m.id].recited.length }));
  const max = Math.max(10, ...vals.map((v) => v.n));
  const H = vals.length * rowH + 10;
  const svg = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img",
    "aria-label": vals.map((v) => `${v.m.name}: ${v.n}`).join(", ") });
  svg.append(svgEl("line", { class: "axisline", x1: x0, x2: x0, y1: 0, y2: H - 6 }));
  vals.forEach((v, i) => {
    const y = 6 + i * rowH;
    const lab = svgEl("text", { class: "rowlab", x: x0 - 10, y: y + 15, "text-anchor": "end" });
    lab.textContent = v.m.name;
    svg.append(lab);
    const w = (x1 - x0) * v.n / max;
    if (w > 0) {
      svg.append(svgEl("path", { d: `M${x0},${y + 6} h${Math.max(0, w - 4)} a4,4 0 0 1 4,4 v4 a4,4 0 0 1 -4,4 h${-Math.max(0, w - 4)} z`, fill: "var(--marigold)" }));
    }
    const t = svgEl("text", { class: "tick", x: x0 + w + 8, y: y + 15 });
    t.textContent = String(v.n);
    t.setAttribute("style", "fill:var(--ink-2);font-size:13px");
    svg.append(t);
  });
  box.append(svg);
  fig.append(el("figcaption", { text: "Gemma 3 1B, Gemma 4 E2B and E4B are Google's; OLMo 2 1B is Ai2's, trained on fully open data." }));
}

const spell = (n) => (n <= 10 ? ["none", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"][n] : fmt(n));
const plural = (n, w) => `${n === 0 ? "no" : spell(n)} ${w}${n === 1 ? "" : "s"}`;

function copiesLede(all) {
  const uo = D.passages["pg932-00"], up = D.passages["pg932-05"];
  if (!uo.web || uo.web.dclm == null) return;
  const body = (m, k) => all.filter((p) => p.kind === "body" && p.web && p.web[k] != null && p.scores[m]);
  const mean = (ps, m) => ps.reduce((s, p) => s + p.scores[m].t, 0) / ps.length;
  const g = body(STAR, "dclm"), many = g.filter((p) => p.web.dclm >= 100), none = g.filter((p) => p.web.dclm === 0);
  const rec = many.filter((p) => p.scores[STAR].g >= D.recited_at).length;
  $("#copies-lede").textContent = `Maybe the models remember what was copied most. That can be checked, because some training data is open, and ` +
    `infini-gram counts exact phrases in trillions of tokens of it. The opening of The Fall of the House of Usher occurs ` +
    `${fmt(uo.web.dclm)} times in DCLM, an open web corpus; a page ${pct(up.pos)} of the way in occurs ${fmt(up.web.dclm)} times. ` +
    `${name(STAR)} recites the first for ${uo.scores[STAR].g} words and predicts only ${pct(up.scores[STAR].t)} of the second. ` +
    `Across the books, ${many.length} random pages occur a hundred times or more. Copies help a little: it predicts ${pct(mean(many, STAR))} ` +
    `of their words, against ${pct(mean(none, STAR))} on pages with no copies at all. But it recites ${rec === 0 ? "none" : "only " + spell(rec)} of them.`;
  const o = body(OLMO, "olmo-mix");
  if (!o.length || !uo.web["olmo-mix"]) return;
  const om = o.filter((p) => p.web["olmo-mix"] >= 100);
  const orec = om.filter((p) => p.scores[OLMO].g >= D.recited_at).length;
  const olong = Math.max(...om.map((p) => p.scores[OLMO].g));
  $("#copies-open").textContent = `DCLM only stands in for Gemma's training data, which is private. OLMo 2's pretraining data is public, so ` +
    `for ${name(OLMO)} the count is exact: ${om.length} random pages occur a hundred times or more in the very text it was pretrained on, and it ` +
    `recites ${spell(orec)} of them; its longest run on any of them is ${plural(olong, "word")}. The opening of Usher occurs ` +
    `${fmt(uo.web["olmo-mix"])} times in that data, and ${name(OLMO)} predicts ${pct(uo.scores[OLMO].t)} of it, about what it manages on a random page.`;
}

function renderWeb() {
  const fig = $("#fig-web");
  const all = Object.values(D.passages);
  const has = (k) => all.some((p) => p.web && p.web[k] != null);
  const pairs = [[STAR, "dclm"], [OLMO, "olmo-mix"]].filter(([m, k]) => D.summary[m] && has(k));
  copiesLede(all);
  figHead(fig, "Copies in open training data vs. share of words predicted",
    "Each dot is a passage. Copies are exact matches of the ten words where the given text meets the continuation, counted with infini-gram.");
  fig.append(keyOf(KINDS.map(([, label, color]) => [label, color])));
  panels(fig, pairs.map(([m, k]) => `${name(m)} vs. ${WEB_NAMES[k] || k}`)).forEach((panel, i) => panel.append(scatter(...pairs[i], widthOf(panel))));
  const bins = [[0, 0, "none"], [1, 9, "1–9"], [10, 99, "10–99"], [100, Infinity, "100 or more"]];
  const rows = [];
  for (const [m, k] of pairs) {
    for (const [kind, label] of KINDS) {
      for (const [lo, hi, bl] of bins) {
        const g = all.filter((p) => p.kind === kind && p.web && p.web[k] != null && p.web[k] >= lo && p.web[k] <= hi && p.scores[m]);
        if (!g.length) continue;
        const mean = g.reduce((s, p) => s + p.scores[m].t, 0) / g.length;
        rows.push([name(m), WEB_NAMES[k] || k, label, bl, g.length, pct(mean), g.filter((p) => p.scores[m].g >= D.recited_at).length]);
      }
    }
  }
  const left = all.filter((p) => !p.web).length;
  fig.append(tableView(["model", "corpus", "passages", "copies", "n", "predicted", "recited"], rows),
    el("figcaption", { text: `The ${fmt(left)} passages whose ten words span a line break are left out: copies break lines in different places, so an exact count would measure formatting.` }));
}

const NOTES = {
  "gemma-4-E4B": [["pg932-00", "Usher, opening"], ["pg932-05", "Usher, a middle page"]],
  "OLMo-2-0425-1B": [["pg932-00", "Usher, opening"], ["pg46-00", "A Christmas Carol, opening"]],
};

function scatter(m, k, W) {
  const H = Math.round(Math.max(250, Math.min(340, W * 0.62))), x0 = 52, x1 = W - 14, y0 = 14, y1 = H - 42, zx = x0 + 26;
  const pts = Object.entries(D.passages).filter(([, p]) => p.web && p.web[k] != null && p.scores[m])
    .map(([id, p]) => ({ id, p, n: p.web[k], t: p.scores[m].t, g: p.scores[m].g }));
  const maxN = Math.max(10, ...pts.map((q) => q.n));
  const lmax = Math.ceil(Math.log10(maxN));
  const X = (n) => (n === 0 ? x0 + 6 : zx + 12 + Math.log10(n) / lmax * (x1 - zx - 12));
  const Y = (t) => y1 - t * (y1 - y0);
  const svg = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img",
    "aria-label": `${name(m)}: words predicted against copies in ${WEB_NAMES[k] || k}` });
  for (const t of [0, 0.25, 0.5, 0.75, 1]) {
    svg.append(svgEl("line", { class: "gridline", x1: x0, x2: x1, y1: Y(t), y2: Y(t) }));
    const tx = svgEl("text", { class: "tick", x: x0 - 8, y: Y(t) + 4, "text-anchor": "end" });
    tx.textContent = pct(t);
    svg.append(tx);
  }
  const xt = [[0, "0"], ...Array.from({ length: lmax + 1 }, (_, i) => [10 ** i, i >= 3 ? `${10 ** (i - 3)}K` : String(10 ** i)])];
  for (const [n, lab] of xt) {
    const tx = svgEl("text", { class: "tick", x: X(n), y: y1 + 18, "text-anchor": "middle" });
    tx.textContent = lab;
    svg.append(tx);
  }
  svg.append(svgEl("line", { class: "axisline", x1: zx, x2: zx, y1: y0, y2: y1 }));
  const xl = svgEl("text", { class: "tick", x: (x0 + x1) / 2, y: H - 4, "text-anchor": "middle" });
  xl.textContent = `copies in ${WEB_NAMES[k] || k}`;
  svg.append(xl);
  const colors = Object.fromEntries(KINDS.map(([kk, , c]) => [kk, c]));
  const order = { body: 0, novel: 1, quoted: 2, opening: 3 };
  pts.sort((a, b) => order[a.p.kind] - order[b.p.kind]);
  // deterministic jitter for the zero column
  const jit = (id) => { let h = 0; for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return (h % 1000) / 1000 - 0.5; };
  for (const q of pts) {
    q.cx = q.n === 0 ? x0 + 8 + jit(q.id) * 20 : X(q.n);
    q.cy = Y(q.t);
    const big = q.p.kind !== "body";
    svg.append(svgEl("circle", { cx: q.cx, cy: q.cy, r: big ? 4.5 : 3, fill: colors[q.p.kind], "fill-opacity": big ? 1 : 0.55,
      stroke: "var(--surface)", "stroke-width": big ? 1.5 : 0.75 }));
  }
  for (const [id, label] of NOTES[m] || []) {
    const q = pts.find((z) => z.id === id);
    if (!q) continue;
    svg.append(svgEl("circle", { cx: q.cx, cy: q.cy, r: 8, fill: "none", stroke: "var(--ink)", "stroke-width": 1 }));
    const t = svgEl("text", { class: "anno", x: q.cx - 12, y: q.cy + (q.t > 0.6 ? 4 : -12), "text-anchor": "end" });
    t.textContent = label;
    svg.append(t);
  }
  const hitLayer = svgEl("rect", { x: x0 - 4, y: y0 - 4, width: x1 - x0 + 8, height: y1 - y0 + 8, fill: "transparent" });
  const ring = svgEl("circle", { r: 7, fill: "none", stroke: "var(--ink)", "stroke-width": 1.5, opacity: 0, "pointer-events": "none" });
  svg.append(hitLayer, ring);
  hitLayer.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    const sx = (e.clientX - r.left) * W / r.width, sy = (e.clientY - r.top) * H / r.height;
    let best = null, bd = 400;
    for (const q of pts) { const d = (q.cx - sx) ** 2 + (q.cy - sy) ** 2; if (d < bd) { bd = d; best = q; } }
    if (!best) { hideTip(); ring.setAttribute("opacity", 0); return; }
    ring.setAttribute("cx", best.cx); ring.setAttribute("cy", best.cy); ring.setAttribute("opacity", 1);
    const w = best.p.work;
    showTip(e, `${pct(best.t)} predicted`, `${w.title}${w.pg ? ", " + (best.p.kind === "opening" ? "opening" : pct(best.p.pos) + " in") : ""}`,
      `${fmt(best.n)} copies · recited ${best.g} words`, `“${best.p.prefix.split(/\s+/).slice(-5).join(" ")} …”`);
  });
  hitLayer.addEventListener("pointerleave", () => { hideTip(); ring.setAttribute("opacity", 0); });
  return svg;
}

/* ---------------- ofrenda ---------------- */

function firstSentences(p, max = 45) {
  const words = (p.prefix + " " + targetWords(p).join(" ")).split(/\s+/);
  let out = [];
  for (const w of words) {
    out.push(w);
    if (out.length >= 12 && /[.!?]["'”’)]*$/.test(w)) break;
    if (out.length >= max) { out.push("…"); break; }
  }
  return out.join(" ").replace(/ …$/, "…");
}

/* where the given words stop: what the book says next, and what the machine wrote instead */
function fork(p, max = 30) {
  if (!p.said) return null;
  const clip = (ws) => ws.slice(0, max).join(" ") + (ws.length > max ? "…" : "");
  const book = targetWords(p), said = p.said.trim().split(/\s+/);
  let n = 0;
  while (n < said.length && n < book.length && said[n] === book[n]) n++;
  return el("div", { class: "fork" },
    el("p", { class: "from", text: "… " + p.prefix.trim().split(/\s+/).slice(-6).join(" ") }),
    el("p", {}, el("span", { class: "lbl", text: "The book" }), clip(book)),
    el("p", {}, el("span", { class: "lbl", text: name(STAR) }),
      n ? el("span", { class: "same", text: said.slice(0, n).join(" ") + " " }) : null,
      el("span", { class: "own", text: clip(said.slice(n)) })));
}

function altarCard(w) {
  const open = D.passages[w.passages.find((id) => D.passages[id].kind === "opening")];
  const best = bestRun(w, STAR);
  return el("article", { class: "ofr" },
    el("div", { class: "name", text: w.author }),
    el("div", { class: "dates", text: `${w.dates.replace("-", "–")} · ${w.title}, ${w.year}` }),
    BIOS[w.pg] ? el("p", { class: "bio", text: BIOS[w.pg] }) : null,
    el("blockquote", { text: firstSentences(open) }),
    fork(open),
    el("div", { class: "nums" },
      el("div", {}, "Downloaded ", el("b", { text: fmt(w.downloads) }), " times in the 30 days to Oct 30, 2026"),
      el("div", {}, "Lines on Wikiquote: ", el("b", { text: String(w.quoted) })),
      el("div", {}, `Longest run ${name(STAR)} recites: `, el("b", { text: `${best} word${best === 1 ? "" : "s"}` }))),
    el("a", { href: `https://www.gutenberg.org/ebooks/${w.pg}`, text: `Read ${w.title} →` }));
}

function renderAltar() {
  const ghosts = new Set(["forgotten", "late"]);
  const longest = Math.max(...Object.values(D.passages).filter((p) => ghosts.has(p.work.tier))
    .flatMap((p) => Object.values(p.scores).map((s) => s.g)));
  const top = Math.max(...Object.values(D.passages).filter((p) => ghosts.has(p.work.tier))
    .flatMap((p) => Object.values(p.scores).map((s) => s.t)));
  for (const n of document.querySelectorAll('[data-n="ghost-run"]')) n.textContent = plural(longest, "word");
  for (const n of document.querySelectorAll('[data-n="ghost-top"]')) n.textContent = pct(top);
  $("#altar").replaceChildren(...D.works.filter((w) => w.tier === "forgotten").map(altarCard));
  $("#late-note").textContent = "Six more ghost books were first posted to Project Gutenberg in 2025 and 2026, after these models' training data was collected. To the machine they read just like the forgotten ones.";
  $("#altar-late").replaceChildren(...D.works.filter((w) => w.tier === "late").map(altarCard));
}

function renderMethodNumbers() {
  const c = D.checks;
  const n = document.querySelector('[data-n="gen"]');
  if (c && n) {
    let s = `${fmt(c.gen_n)} passages: every one with a run of five words or more, plus ${fmt(c.gen_random)} chosen at random. The generated text kept to the book for exactly the measured number of words in ${fmt(c.gen_agree)} of them`;
    if (c.gen_n > c.gen_agree) {
      s += `; in ${spell(c.gen_longer)} it went further, and in ${spell(c.gen_shorter)} it stopped sooner`;
    }
    n.textContent = s;
  }
}
