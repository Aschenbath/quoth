"""Fetch Project Gutenberg texts and normalize them into plain paragraphs.

Normalization (documented in PROTOCOL.md, applied identically to every work):
  * keep only the text between the "*** START OF" and "*** END OF" markers
  * drop [Illustration ...] notes and footnote markers like [1]
  * unwrap hard-wrapped prose lines; verse-like blocks keep their line breaks
  * remove _underscore_ italics, straighten curly quotes, collapse runs of spaces
  * a small-caps chapter opening ("MARLEY was dead") becomes "Marley was dead"
Paragraphs are joined with a blank line.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

URL = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
START_RE = re.compile(r"^\*\*\* ?START OF (?:THE|THIS) PROJECT GUTENBERG E-?BOOK.*$", re.M | re.I)
END_RE = re.compile(r"^\*\*\* ?END OF (?:THE|THIS) PROJECT GUTENBERG E-?BOOK.*$", re.M | re.I)
QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def fetch(pg_id: int, cache: Path, delay: float = 2.0) -> str:
    """Download (once) and return the raw UTF-8 text of a Gutenberg ebook."""
    path = cache / f"pg{pg_id}.txt"
    if not path.exists():
        req = urllib.request.Request(URL.format(id=pg_id), headers={"User-Agent": "quoth/0.1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            path.write_bytes(r.read())
        time.sleep(delay)
    return path.read_text(encoding="utf-8-sig")


def _is_verse(lines: list[str]) -> bool:
    """Verse lines start with a capital; wrapped prose lines mostly do not."""
    if len(lines) < 2:
        return False
    lengths = [len(l.strip()) for l in lines]
    if max(lengths) > 80:
        return False
    starts = [l.strip()[0] for l in lines[1:]]
    upper = sum(c.isupper() or c in "\"'(" for c in starts) / len(starts)
    # a two-line prose paragraph can start its second line with a capital by chance,
    # but its first line is then filled out to the usual wrap width
    return upper >= 0.75 and (len(lines) >= 3 or lengths[0] < 60)


SMALL = {"a", "an", "the", "and", "but", "or", "of", "in", "on", "at", "to", "as", "it", "is",
         "was", "had", "have", "he", "she", "we", "they", "his", "her", "my", "this", "that"}


def _uncap_opening(par: str) -> str:
    """Printers set a chapter's first word or two in capitals: "MARLEY was dead"."""
    m = re.match(r"((?:[A-Z][A-Z'’]*[,;:.!?]?\s+)+)(?=[a-z])", par)
    if not m or not any(len(w.strip(",;:.!?")) > 1 for w in m.group(1).split()):
        return par
    words = m.group(1).split(" ")
    fixed = []
    for k, w in enumerate(words):
        low = w.lower()
        if low.strip(",;:.!?") == "i":
            fixed.append(w)
        elif k > 0 and low.strip(",;:.!?") in SMALL:
            fixed.append(low)
        else:
            fixed.append(w[:1] + low[1:])
    return " ".join(fixed) + par[m.end(1):]


def normalize(raw: str) -> str:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    s, e = START_RE.search(raw), END_RE.search(raw)
    body = raw[s.end() if s else 0 : e.start() if e else len(raw)]
    body = re.sub(r"\[Illustration[^\]]*\]", "", body, flags=re.S)
    body = re.sub(r"\[\d+\]", "", body)
    body = body.replace("_", "").translate(QUOTES)

    pars = []
    for block in re.split(r"\n\s*\n", body):
        lines = [l.rstrip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        if _is_verse(lines):
            par = "\n".join(re.sub(r" {2,}", " ", l.strip()) for l in lines)
        else:
            par = re.sub(r"\s+", " ", " ".join(l.strip() for l in lines))
        pars.append(_uncap_opening(par))
    return "\n\n".join(pars)


def load_works(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["works"]


def narrative(text: str, work: dict) -> str:
    """Cut a normalized text to the narrative: from the `start` phrase to the `end` phrase."""
    a = text.find(work["start"]) if work.get("start") else 0
    if a < 0:
        raise ValueError(f"start phrase not found for pg{work['pg']}: {work['start']!r}")
    b = len(text)
    if work.get("end"):
        b = text.find(work["end"], a)
        if b < 0:
            raise ValueError(f"end phrase not found for pg{work['pg']}: {work['end']!r}")
    return text[a:b].rstrip()
