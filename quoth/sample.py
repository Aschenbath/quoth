"""Draw the passages to score: a fixed, seeded sample from every work.

A passage is PREFIX_WORDS words of real text followed by the TARGET_WORDS words
the model has to produce. For each work:

* passage 00 starts at the first word of the narrative (its opening);
* the rest of the text is cut into equal strata with one passage per stratum,
  starting at a random sentence start inside it (seeded by the work's id),

so passages are spread evenly from first page to last and never overlap.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

PREFIX_WORDS = 40
TARGET_WORDS = 50
SPAN = PREFIX_WORDS + TARGET_WORDS
MAX_PER_WORK = 30
WORDS_PER_PASSAGE = 200  # short works get one passage per 200 words
SEED = 20261031

WORD_RE = re.compile(r"\S+")
HEADING_RE = re.compile(r"(?:\b[A-Z][A-Z'\-]+\b[ .,:;\n]*){3,}")
ABBREV = {"Mr.", "Mrs.", "Dr.", "St.", "Mme.", "Mlle.", "M.", "Messrs.", "Col.", "Capt.", "Rev.", "Prof."}


def _sentence_start(text: str, words: list[tuple[int, int]], i: int) -> bool:
    if i == 0:
        return True
    ps, pe = words[i - 1]
    if "\n\n" in text[pe : words[i][0]]:
        return True
    prev, cur = text[ps:pe], text[words[i][0] : words[i][1]]
    if prev in ABBREV or re.fullmatch(r"[A-Z]\.", prev):
        return False
    return bool(re.search(r"[.!?][\"')\]]*$", prev)) and bool(re.match(r"[\"'(]*[A-Z]", cur))


def _passage(text: str, words: list[tuple[int, int]], a: int) -> dict:
    b = a + PREFIX_WORDS
    return {
        "prefix": text[words[a][0] : words[b - 1][1]],
        "sep": text[words[b - 1][1] : words[b][0]],
        "target": text[words[b][0] : words[a + SPAN - 1][1]],
    }


def sample_work(work: dict, text: str) -> list[dict]:
    words = [(m.start(), m.end()) for m in WORD_RE.finditer(text)]
    n = len(words)
    k = min(MAX_PER_WORK, n // WORDS_PER_PASSAGE)
    rng = random.Random(f"{SEED}-{work['pg']}")
    starts = [0]
    lo_all, hi_all = SPAN, n - SPAN
    for j in range(k - 1):
        lo = lo_all + j * (hi_all - lo_all) // (k - 1)
        hi = lo_all + (j + 1) * (hi_all - lo_all) // (k - 1) - SPAN
        window = range(lo, max(lo, hi) + 1)

        def clean(a: int) -> bool:
            span = text[words[a][0] : words[a + SPAN - 1][1]]
            return not HEADING_RE.search(span)

        cands = [a for a in window if _sentence_start(text, words, a) and clean(a)]
        cands = cands or [a for a in window if clean(a)]
        if cands:
            starts.append(rng.choice(cands))

    out = []
    for j, a in enumerate(starts):
        out.append({
            "id": f"pg{work['pg']}-{j:02d}",
            "pg": work["pg"],
            "tier": work["tier"],
            "kind": "opening" if j == 0 else "body",
            "word": a,
            "pos": round(a / n, 4),
            **_passage(text, words, a),
        })
    return out


def find_quotes(text: str, lines: list[tuple[str, str]]) -> list[dict]:
    """Where each (source page, quoted line) occurs in the text (see quotes.py).
    Lines inside the opening passage or within ten words of an earlier find are
    skipped."""
    from .quotes import Index

    words = [(m.start(), m.end()) for m in WORD_RE.finditer(text)]
    index, found = Index(text, words), []
    for page, line in lines:
        hit = index.locate(line, TARGET_WORDS)
        if not hit or hit[0] < SPAN or any(abs(hit[0] - f["word"]) < 10 for f in found):
            continue
        found.append({"word": hit[0], "words": hit[1] - hit[0], "quote": line, "source": page})
    return sorted(found, key=lambda f: f["word"])


def sample_quoted(work: dict, text: str, found: list[dict]) -> list[dict]:
    """A quoted passage: the 40 words before the quote, then the quote itself."""
    words = [(m.start(), m.end()) for m in WORD_RE.finditer(text)]
    out = []
    for j, f in enumerate(found):
        a, n = f["word"], f["words"]
        out.append({
            "id": f"pg{work['pg']}-q{j:02d}",
            "pg": work["pg"],
            "tier": work["tier"],
            "kind": "quoted",
            "word": a - PREFIX_WORDS,
            "pos": round(a / len(words), 4),
            "prefix": text[words[a - PREFIX_WORDS][0] : words[a - 1][1]],
            "sep": text[words[a - 1][1] : words[a][0]],
            "target": text[words[a][0] : words[a + n - 1][1]],
        })
    return out


def read_controls(path: Path) -> list[dict]:
    """Blocks headed by '=== id' lines; anything before the first header is a note."""
    parts = re.split(r"^=== (\S+)\n", path.read_text(encoding="utf-8"), flags=re.M)
    return [{"id": parts[i], "text": parts[i + 1].strip()} for i in range(1, len(parts), 2)]


def sample_controls(controls: list[dict]) -> list[dict]:
    """Freshly written passages: split each into the same prefix/target shape."""
    out = []
    for c in controls:
        words = [(m.start(), m.end()) for m in WORD_RE.finditer(c["text"])]
        if len(words) < SPAN:
            raise ValueError(f"control {c['id']} has only {len(words)} words")
        out.append({"id": c["id"], "pg": None, "tier": "novel", "kind": "novel",
                    "word": 0, "pos": 0.0, **_passage(c["text"], words, 0)})
    return out


def write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
