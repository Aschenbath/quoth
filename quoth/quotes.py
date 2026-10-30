"""The lines people quote: Wikiquote entries located in the Gutenberg text.

Wikiquote is a community list of the lines readers found worth repeating. For
every work we take the level-1 bullets (the quotes themselves; deeper bullets
are sources and commentary) from the pages fetched for it, strip the wiki
markup, and look for each quote in the normalized Gutenberg text. A quote counts
as found when its first six words occur in order (ignoring case and punctuation)
and the text from there matches the quote (up to its first 50 words, or up to
an ellipsis) with a difflib similarity of at least 0.8.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from .corpus import QUOTES

LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
REF = re.compile(r"<ref[^>]*?/>|<ref[^>]*>.*?</ref>", re.S)
TAG = re.compile(r"<[^>]+>")
ELLIPSIS = re.compile(r"\.\s?\.\s?\.|…")


def clean(line: str) -> str:
    s = REF.sub("", line.lstrip("*").strip())
    for _ in range(3):
        s = TEMPLATE.sub("", s)
    s = LINK.sub(r"\1", s).replace("'''", "").replace("''", "")
    s = TAG.sub(" ", s).translate(QUOTES).replace("_", "")
    return re.sub(r"\s+", " ", s).strip()


def wikiquote_lines(wikitext: str, min_words: int = 8) -> list[str]:
    out = []
    for line in wikitext.split("\n"):
        if line.startswith("*") and not line.startswith("**"):
            s = clean(line)
            if len(s.split()) >= min_words:
                out.append(s)
    return out


def _key(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


class Index:
    """Word keys of a text (lowercase, punctuation stripped) for quote lookup."""

    def __init__(self, text: str, words: list[tuple[int, int]]):
        keys = [_key(text[a:b]) for a, b in words]
        self.pos = [i for i, k in enumerate(keys) if k]
        self.keys = [keys[i] for i in self.pos]
        self.first: dict[str, list[int]] = {}
        for j, k in enumerate(self.keys):
            self.first.setdefault(k, []).append(j)

    def locate(self, quote: str, limit: int = 50) -> tuple[int, int] | None:
        """Text word span [start, end) of the quote's first `limit` words, or None."""
        head = ELLIPSIS.split(quote)[0]
        q = [k for k in map(_key, head.split()) if k][:limit]
        if len(q) < 8:
            return None
        for j in self.first.get(q[0], []):
            got = self.keys[j : j + len(q)]
            if got[:6] == q[:6] and SequenceMatcher(None, got, q, autojunk=False).ratio() >= 0.8:
                return self.pos[j], self.pos[j + len(got) - 1] + 1
        return None
