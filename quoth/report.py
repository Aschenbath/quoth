"""Aggregate scored passages into the tables in the write-up and the site's data.

  python -m quoth report --site docs/data.json
"""

from __future__ import annotations

import json
from pathlib import Path

import torch

from . import corpus, sample
from .web import crosses_break

MODELS = [
    ("gemma-3-1b-pt", "Gemma 3 1B"),
    ("gemma-4-E2B", "Gemma 4 E2B"),
    ("gemma-4-E4B", "Gemma 4 E4B"),
    ("OLMo-2-0425-1B", "OLMo 2 1B"),
]
GENERATED = "gemma-4-E4B"  # the model whose greedy continuations were generated (PROTOCOL.md, step 4)
RECITED = 10  # greedy_words at or above this counts as recited (PROTOCOL.md)
KNOWN = 0.8  # top1_words at or above this: added after the main run, because a stray dash cannot break it (PROTOCOL.md)
TIERS = ["canon", "genre", "forgotten", "late", "novel"]
KINDS = ["opening", "body", "quoted", "novel"]


def bootstrap(xs: list[float], n: int = 10_000, seed: int = sample.SEED) -> tuple[float, float]:
    """95% percentile bootstrap interval for the mean."""
    if len(xs) < 2:
        return (xs[0], xs[0]) if xs else (float("nan"), float("nan"))
    g = torch.Generator().manual_seed(seed)
    t = torch.tensor(xs, dtype=torch.float64)
    means = t[torch.randint(len(xs), (n, len(xs)), generator=g)].mean(dim=1)
    lo, hi = torch.quantile(means, torch.tensor([0.025, 0.975], dtype=torch.float64)).tolist()
    return lo, hi


def load_results(results: Path) -> dict[str, dict[str, dict]]:
    """{model id: {passage id: row}} for every model with a results file."""
    out = {}
    for mid, _ in MODELS:
        f = results / f"{mid}.jsonl"
        if f.exists():
            out[mid] = {r["id"]: r for r in sample.read_jsonl(f)}
    return out


def group_stats(rows: list[dict]) -> dict:
    top1 = [r["top1_words"] for r in rows]
    lo, hi = bootstrap(top1)
    return {
        "n": len(rows),
        "recited": sum(r["greedy_words"] >= RECITED for r in rows),
        "known": sum(r["top1_words"] >= KNOWN for r in rows),
        "max_greedy": max(r["greedy_words"] for r in rows),
        "max_top1": max(top1),
        "top1": round(sum(top1) / len(top1), 4),
        "top1_ci": [round(lo, 4), round(hi, 4)],
    }


def summarize(passages: list[dict], res: dict[str, dict[str, dict]]) -> dict:
    """Per model: stats by kind, by tier x kind, and the recited passages."""
    out = {}
    for mid, by_id in res.items():
        rows = [(p, by_id[p["id"]]) for p in passages if p["id"] in by_id]
        kinds = {k: group_stats([r for p, r in rows if p["kind"] == k]) for k in KINDS
                 if any(p["kind"] == k for p, _ in rows)}
        cells = {}
        for t in TIERS:
            for k in KINDS:
                g = [r for p, r in rows if p["tier"] == t and p["kind"] == k]
                if g:
                    cells[f"{t}/{k}"] = group_stats(g)
        recited = sorted(((r["greedy_words"], p["id"]) for p, r in rows if r["greedy_words"] >= RECITED), reverse=True)
        tiers = {t: group_stats([r for p, r in rows if p["tier"] == t]) for t in TIERS
                 if any(p["tier"] == t for p, _ in rows)}
        out[mid] = {"n": len(rows), "kinds": kinds, "cells": cells, "tiers": tiers,
                    "recited": [{"id": i, "words": g} for g, i in recited]}
    return out


def _md_table(head: list[str], body: list[list]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in body]
    return "\n".join(lines)


def tables(summary: dict, names: dict[str, str]) -> str:
    parts = []
    head = ["model"] + [k for k in KINDS]
    body = []
    for mid, s in summary.items():
        body.append([names[mid]] + [f"{s['kinds'][k]['recited']} / {s['kinds'][k]['n']}" if k in s["kinds"] else ""
                                    for k in KINDS])
    parts.append("Recited passages (greedy run >= %d words)\n\n" % RECITED + _md_table(head, body))
    body = [[names[mid]] + [f"{s['tiers'][t]['known']} / {s['tiers'][t]['n']} (best {s['tiers'][t]['max_top1']:.2f})" for t in TIERS]
            for mid, s in summary.items()]
    parts.append(f"Passages with top-1 >= {KNOWN} (and the best top-1 in the tier)\n\n" + _md_table(["model"] + TIERS, body))
    for mid, s in summary.items():
        body = []
        for t in TIERS:
            row = [t]
            for k in KINDS:
                c = s["cells"].get(f"{t}/{k}")
                row.append(f"{c['top1']:.3f} [{c['top1_ci'][0]:.3f}, {c['top1_ci'][1]:.3f}] n={c['n']}" if c else "")
            body.append(row)
        parts.append(f"{names[mid]}: mean top-1 word accuracy [95% CI]\n\n" + _md_table(["tier"] + KINDS, body))
    return "\n\n".join(parts)


COPY_BINS = [(0, 0, "0"), (1, 9, "1-9"), (10, 99, "10-99"), (100, None, "100+")]
CORPUS_FOR = {"OLMo-2-0425-1B": "olmo-mix"}  # a model's own training data where it is public; DCLM otherwise


def copies_table(passages: list[dict], res: dict, web: dict[str, dict[str, int]]) -> str:
    """Prediction by how often the passage's seam occurs in an open corpus."""
    rows = []
    for mid, by_id in res.items():
        name = CORPUS_FOR.get(mid, "dclm")
        counts = web.get(name, {})
        for kind in KINDS:
            for lo, hi, label in COPY_BINS:
                g = [by_id[p["id"]] for p in passages
                     if p["kind"] == kind and p["id"] in by_id and p["id"] in counts and not crosses_break(p)
                     and counts[p["id"]] >= lo and (hi is None or counts[p["id"]] <= hi)]
                if g:
                    rows.append([mid, name, kind, label, len(g), f"{sum(r['top1_words'] for r in g) / len(g):.3f}",
                                 sum(r["greedy_words"] >= RECITED for r in g), max(r["greedy_words"] for r in g)])
    return ("Copies of each passage's seam in an open corpus (seams across a line break left out)\n\n"
            + _md_table(["model", "corpus", "kind", "copies", "n", "top-1", "recited", "longest run"], rows))


def _split_words(text: str) -> list[str]:
    """Alternating [word, gap, word, gap, ...] so the site needs no tokenizer."""
    out, last = [], 0
    for m in sample.WORD_RE.finditer(text):
        if out:
            out.append(text[last:m.start()])
        out.append(m.group())
        last = m.end()
    return out


def generation_check(gens: dict[str, dict]) -> dict:
    """How often greedy generation kept to the text for exactly the teacher-forced run."""
    rows = list(gens.values())
    return {
        "model": GENERATED,
        "gen_n": len(rows),
        "gen_random": sum(r["tf_words"] < 5 for r in rows),
        "gen_agree": sum(r["gen_words"] == r["tf_words"] for r in rows),
        "gen_longer": sum(r["gen_words"] > r["tf_words"] for r in rows),
        "gen_shorter": sum(r["gen_words"] < r["tf_words"] for r in rows),
        "differ": [{"id": r["id"], "gen": r["gen_words"], "tf": r["tf_words"]} for r in rows if r["gen_words"] != r["tf_words"]],
    }


def site_data(works: list[dict], passages: list[dict], res: dict, summary: dict,
              web: dict[str, dict[str, int]], gens: dict[str, dict], quotes: dict, said: dict[str, dict],
              recall: dict[str, dict], raven: dict | None) -> dict:
    names = dict(MODELS)
    by_pg: dict = {}
    for p in passages:
        by_pg.setdefault(p["pg"], []).append(p["id"])
    out_passages = {}
    for p in passages:
        scores = {}
        for mid, by_id in res.items():
            r = by_id.get(p["id"])
            if r:
                scores[mid] = {"g": r["greedy_words"], "t": r["top1_words"], "h": r["word_hit"]}
        row = {"kind": p["kind"], "pos": p["pos"], "prefix": p["prefix"], "sep": p["sep"],
               "target": _split_words(p["target"]), "scores": scores}
        for name, counts in web.items():
            if p["id"] in counts and not crosses_break(p):
                row.setdefault("web", {})[name] = counts[p["id"]]
        if p["id"] in said:
            row["said"] = said[p["id"]]["generated"]
        if p["id"] in recall:
            row["recall"] = {k: v for k, v in recall[p["id"]].items() if k in ("words", "said_words", "passed", "pieces")}
        if p["kind"] == "quoted":
            q = quotes[str(p["pg"])][int(p["id"].rsplit("-q", 1)[1])]
            row["source"] = q["source"]
        out_passages[p["id"]] = row
    out_works = [{k: w[k] for k in ("pg", "tier", "title", "author", "dates", "year", "downloads", "released")
                  if k in w} | {"passages": by_pg.get(w["pg"], []), "quoted": len(quotes.get(str(w["pg"]), []))}
                 for w in works]
    out_works.append({"pg": None, "tier": "novel", "title": "Written yesterday", "author": "control passages",
                      "passages": by_pg.get(None, []), "quoted": 0})
    return {"models": [{"id": m, "name": names[m]} for m in res], "recited_at": RECITED,
            "works": out_works, "passages": out_passages, "summary": summary,
            "checks": generation_check(gens) if gens else None, "raven": raven}


def main(results: str = "results", site: str | None = None, data: str = "data") -> None:
    works = corpus.load_works(Path(data) / "works.json")
    passages = sample.read_jsonl(Path(data) / "passages.jsonl")
    quotes = json.loads((Path(data) / "quotes.json").read_text(encoding="utf-8"))
    res = load_results(Path(results))
    summary = summarize(passages, res)
    print(tables(summary, dict(MODELS)))
    gen_file = Path(results) / f"{GENERATED}.gen.jsonl"
    gens = {r["id"]: r for r in sample.read_jsonl(gen_file)} if gen_file.exists() else {}
    if gens:
        c = generation_check(gens)
        print(f"\nGreedy generation ({dict(MODELS)[GENERATED]}, {c['gen_n']} passages): same run as teacher forcing in "
              f"{c['gen_agree']}, longer in {c['gen_longer']}, shorter in {c['gen_shorter']}: {c['differ']}")
    web = {}
    for f in sorted(Path(results).glob("web-*.jsonl")):
        web[f.stem.removeprefix("web-")] = {r["id"]: r["count"] for r in sample.read_jsonl(f)}
    if web:
        print("\n" + copies_table(passages, res, web))
    if site:
        # the forgotten openings were generated for the site alone, so they stay out of the check above
        extra = Path(results) / f"{GENERATED}.ofrenda.jsonl"
        said = {r["id"]: r for r in sample.read_jsonl(extra)} if extra.exists() else {}
        recall_file = Path(results) / f"{GENERATED}.recall.jsonl"
        recall = {r["id"]: r for r in sample.read_jsonl(recall_file)} if recall_file.exists() else {}
        raven_file = Path(results) / f"{GENERATED}.raven-1845.jsonl"
        raven = sample.read_jsonl(raven_file)[0] if raven_file.exists() else None
        out = site_data(works, passages, res, summary, web, gens, quotes, said | gens, recall, raven)
        Path(site).parent.mkdir(parents=True, exist_ok=True)
        Path(site).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"\nsite data -> {site} ({Path(site).stat().st_size / 1e6:.2f} MB)")
