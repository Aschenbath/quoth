"""quoth: measure which texts an open-weight language model can recite verbatim.

  python -m quoth sample   --works data/works.json --cache CACHE --out data/passages.jsonl
  python -m quoth score    --model MODEL_DIR --passages data/passages.jsonl --out results/NAME.jsonl
  python -m quoth generate --model MODEL_DIR --passages data/passages.jsonl --scores results/NAME.jsonl --out results/NAME.gen.jsonl
  python -m quoth web      --index v4_dclm-baseline_llama --out results/web-dclm.jsonl
  python -m quoth recite   --model MODEL_DIR --text any_book.txt
  python -m quoth report   --site docs/data.json
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import re
import sys
import time
from pathlib import Path

from . import corpus, sample


def cmd_quotes(a: argparse.Namespace) -> None:
    """Locate Wikiquote lines in each work and save them to data/quotes.json."""
    from .quotes import wikiquote_lines

    lines = []
    for f in sorted(Path(a.wikiquote).glob("*.wiki")):
        lines += [(f.stem, line) for line in wikiquote_lines(f.read_text(encoding="utf-8"))]
    out = {}
    for w in corpus.load_works(Path(a.works)):
        text = corpus.narrative(corpus.normalize(corpus.fetch(w["pg"], Path(a.cache))), w)
        found = sample.find_quotes(text, lines)
        print(f"pg{w['pg']:<6} {w['tier']:<9} {len(found):>2} quoted lines  {w['title']}")
        if found:
            out[str(w["pg"])] = found
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{sum(map(len, out.values()))} quoted lines from {len(lines)} Wikiquote entries -> {a.out}")


def cmd_sample(a: argparse.Namespace) -> None:
    quotes = json.loads(Path(a.quotes).read_text(encoding="utf-8")) if a.quotes and Path(a.quotes).exists() else {}
    rows = []
    for w in corpus.load_works(Path(a.works)):
        text = corpus.narrative(corpus.normalize(corpus.fetch(w["pg"], Path(a.cache))), w)
        got = sample.sample_work(w, text)
        got += sample.sample_quoted(w, text, quotes.get(str(w["pg"]), []))
        print(f"pg{w['pg']:<6} {w['tier']:<9} {len(text.split()):>7} words  {len(got):>2} passages  {w['title']}")
        rows += got
    if a.controls:
        rows += sample.sample_controls(sample.read_controls(Path(a.controls)))
    sample.write_jsonl(rows, Path(a.out))
    print(f"{len(rows)} passages -> {a.out}")


def _todo(a: argparse.Namespace, out: Path) -> list[dict]:
    rows = sample.read_jsonl(Path(a.passages))
    if a.ids:
        keep = set(a.ids.split(","))
        rows = [r for r in rows if r["id"] in keep or str(r["pg"]) in keep or r["tier"] in keep]
    done = {r["id"] for r in sample.read_jsonl(out)} if out.exists() else set()
    rows = [r for r in rows if r["id"] not in done]
    return rows[: a.limit] if a.limit else rows


def _write_meta(a: argparse.Namespace, out: Path, lm_name: str) -> None:
    import torch
    import transformers

    meta = {
        "model": lm_name,
        "model_dir": Path(a.model).name,  # folder name only; the full path is local to the machine
        "dtype": a.dtype,
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "python": platform.python_version(),
        "machine": platform.processor() or platform.machine(),
        "threads": torch.get_num_threads(),
        "passages": str(a.passages),
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def cmd_score(a: argparse.Namespace) -> None:
    from .score import load, score

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    todo = _todo(a, out)
    if not todo:
        print("nothing to do")
        return
    lm = load(a.model, a.dtype, mmap=a.mmap)
    _write_meta(a, out, lm.name)
    t0 = time.perf_counter()
    with out.open("a", encoding="utf-8", newline="\n") as f:
        for i, p in enumerate(todo, 1):
            r = score(lm, p["prefix"], p["sep"], p["target"])
            f.write(json.dumps({"id": p["id"], **r}, ensure_ascii=False) + "\n")
            f.flush()
            if i % 50 == 0 or i == len(todo):
                rate = (time.perf_counter() - t0) / i
                print(f"  {i}/{len(todo)}  {rate:.2f}s/passage  last {p['id']} greedy={r['greedy_words']}", flush=True)


def cmd_generate(a: argparse.Namespace) -> None:
    """Greedy-decode from the prefix to check the teacher-forced numbers and to
    record what the model wrote instead of the real text."""
    from .score import generate, leading_word_matches, load

    out = Path(a.out)
    passages = {p["id"]: p for p in sample.read_jsonl(Path(a.passages))}
    scores = sample.read_jsonl(Path(a.scores))
    rng = random.Random(sample.SEED)
    chosen = [s for s in scores if s["greedy_words"] >= a.min_words]
    rest = [s for s in scores if s["greedy_words"] < a.min_words]
    chosen += rng.sample(rest, min(a.random, len(rest)))
    done = {r["id"] for r in sample.read_jsonl(out)} if out.exists() else set()
    chosen = [s for s in chosen if s["id"] not in done]
    if not chosen:
        print("nothing to do")
        return
    lm = load(a.model, a.dtype, mmap=a.mmap)
    with out.open("a", encoding="utf-8", newline="\n") as f:
        for i, s in enumerate(chosen, 1):
            p = passages[s["id"]]
            t = time.perf_counter()
            g = generate(lm, p["prefix"], s["n_tok"] + 8)
            n = leading_word_matches(g, p["target"])
            row = {"id": s["id"], "model": lm.name, "generated": g, "gen_words": n,
                   "tf_words": s["greedy_words"], "agree": n == s["greedy_words"],
                   "secs": round(time.perf_counter() - t, 2)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  {i}/{len(chosen)} {s['id']} generated={n} teacher-forced={s['greedy_words']}", flush=True)


def cmd_web(a: argparse.Namespace) -> None:
    """Count each passage's seam in an open corpus (see web.py). Resumable."""
    from .web import count, seam

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    todo = _todo(a, out)
    with out.open("a", encoding="utf-8", newline="\n") as f:
        for i, p in enumerate(todo, 1):
            q = seam(p)
            row = {"id": p["id"], "index": a.index, "seam": q, "count": count(q, a.index)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if i % 100 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  last {p['id']} count={row['count']}", flush=True)
            time.sleep(a.delay)


def cmd_recite(a: argparse.Namespace) -> None:
    """Probe any text: one passage every --every words, print what the model recites."""
    from .score import load, score

    raw = Path(a.text).read_text(encoding="utf-8-sig")
    text = corpus.normalize(raw) if corpus.START_RE.search(raw) else raw
    words = [(m.start(), m.end()) for m in sample.WORD_RE.finditer(text)]
    anchors = range(0, len(words) - sample.SPAN, a.every)
    lm = load(a.model, a.dtype, mmap=a.mmap)
    best, total = None, 0
    for k in anchors:
        p = sample._passage(text, words, k)
        r = score(lm, p["prefix"], p["sep"], p["target"])
        total += 1
        recited = " ".join(p["target"].split()[: r["greedy_words"]])
        print(f"word {k:>7}  verbatim {r['greedy_words']:>2}/{r['n_words']}  top-1 {r['top1_words']:.2f}  {recited[:70]!r}")
        if best is None or r["greedy_words"] > best[0]:
            best = (r["greedy_words"], k, recited)
    if best:
        print(f"\n{total} passages. Longest verbatim continuation: {best[0]} words at word {best[1]}:\n  {best[2]}")


def cmd_report(a: argparse.Namespace) -> None:
    from .report import main as report

    report(results=a.results, site=a.site, data=a.data)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="quoth", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sample", help="fetch the works and draw the seeded passage sample")
    s.add_argument("--works", default="data/works.json")
    s.add_argument("--controls", default="data/controls_novel.txt")
    s.add_argument("--quotes", default="data/quotes.json")
    s.add_argument("--cache", required=True, help="directory for downloaded Gutenberg texts")
    s.add_argument("--out", default="data/passages.jsonl")
    s.set_defaults(fn=cmd_sample)

    s = sub.add_parser("quotes", help="locate Wikiquote lines in the works")
    s.add_argument("--wikiquote", required=True, help="directory of fetched Wikiquote .wiki pages")
    s.add_argument("--works", default="data/works.json")
    s.add_argument("--cache", required=True)
    s.add_argument("--out", default="data/quotes.json")
    s.set_defaults(fn=cmd_quotes)

    for name, fn, hlp in [("score", cmd_score, "teacher-forced scoring of every passage"),
                          ("generate", cmd_generate, "greedy decoding to verify and show divergences")]:
        s = sub.add_parser(name, help=hlp)
        s.add_argument("--model", required=True, help="local model directory (Hugging Face format)")
        s.add_argument("--dtype", default="bfloat16")
        s.add_argument("--mmap", action="store_true", help="map weights from disk instead of copying them into RAM")
        s.add_argument("--passages", default="data/passages.jsonl")
        s.add_argument("--out", required=True)
        s.add_argument("--ids", help="comma-separated passage ids, Gutenberg numbers or tiers")
        s.add_argument("--limit", type=int)
        if name == "generate":
            s.add_argument("--scores", required=True)
            s.add_argument("--min-words", type=int, default=5, help="always generate when teacher-forced run >= this")
            s.add_argument("--random", type=int, default=60, help="plus this many seeded random other passages")
        s.set_defaults(fn=fn)

    s = sub.add_parser("web", help="count each passage's seam in an open corpus (infini-gram)")
    s.add_argument("--index", default="v4_dclm-baseline_llama")
    s.add_argument("--passages", default="data/passages.jsonl")
    s.add_argument("--out", required=True)
    s.add_argument("--ids")
    s.add_argument("--limit", type=int)
    s.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    s.set_defaults(fn=cmd_web)

    s = sub.add_parser("recite", help="probe any text file for verbatim memory")
    s.add_argument("--model", required=True)
    s.add_argument("--dtype", default="bfloat16")
    s.add_argument("--mmap", action="store_true")
    s.add_argument("--text", required=True)
    s.add_argument("--every", type=int, default=500, help="words between probes")
    s.set_defaults(fn=cmd_recite)

    s = sub.add_parser("report", help="summary tables, and the site's data.json with --site")
    s.add_argument("--results", default="results")
    s.add_argument("--data", default="data")
    s.add_argument("--site", help="write the site data here, e.g. docs/data.json")
    s.set_defaults(fn=cmd_report)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
