"""How far a long generation keeps to the book, read generously.

`greedy_words` (PROTOCOL.md) stops at the first difference of any kind, so a dash
printed as two hyphens ends a run. This reads on: words are compared without their
punctuation or case, a dash separates two words however it is printed, and a small
slip of a word or two is passed over if the next AGREE words line up again. It
reports how much of the book the model reproduces, not how exactly it prints it.

A model that loses its place sometimes picks up the book somewhere else, so the
generation is also split into pieces: stretches of at least LEAST words that follow
the book from wherever they start, with the paragraph (or stanza) each one spans.
None of this is one of the frozen measures; see "Changes after freezing" in PROTOCOL.md.
"""

from __future__ import annotations

import bisect
import re

WORD = re.compile(r"(?:(?!--)[^\s—–])+")
BLOCK = re.compile(r"\n[ \t]*\n\s*")  # a blank line ends a paragraph or a stanza
KEY = 12  # how many words of the prefix it takes to find a passage in its book
SEED_WORDS = 4  # a piece starts where this many words appear together in the book
LEAST = 8  # shorter stretches are left out of the pieces
AGREE = 3  # words that must line up again after a slip
SLIPS = [(1, 1), (0, 1), (1, 0), (1, 2), (2, 1), (2, 2), (0, 2), (2, 0)]  # words passed over, in `said` and in the book


def _bare(word: str) -> str:
    return re.sub(r"\W", "", word).lower()


def spans(text: str) -> list[re.Match]:
    return [m for m in WORD.finditer(text) if _bare(m.group())]


def follow(said: list[str], book: list[str]) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    """How far `said` keeps to `book`: the words used up on each side, and each slip passed
    over as (said from, said to, book from, book to)."""
    a, b = [_bare(w) for w in said], [_bare(w) for w in book]
    i = j = 0
    passed = []
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i, j = i + 1, j + 1
            continue
        for di, dj in SLIPS:
            again = a[i + di:i + di + AGREE]
            if len(again) == AGREE and again == b[j + dj:j + dj + AGREE]:
                passed.append((i, i + di, j, j + dj))
                i, j = i + di, j + dj
                break
        else:
            break
    return i, j, passed


def locate(prefix: str, book: list[str]) -> int:
    """Index in `book` of the word right after `prefix`."""
    key = [_bare(m.group()) for m in spans(prefix)[-KEY:]]
    bare = [_bare(w) for w in book]
    for i in range(len(bare) - KEY):
        if bare[i:i + KEY] == key:
            return i + KEY
    raise ValueError(f"prefix not found: {' '.join(key)}")


def pieces(said: list[str], book: list[str], start: int) -> list[dict]:
    """Stretches of `said` that follow `book`, in the order they were written.
    `start` is where the book continues, preferred when two places fit as well."""
    bare = [_bare(w) for w in book]
    seeds: dict[tuple, list[int]] = {}
    for j in range(len(bare) - SEED_WORDS + 1):
        seeds.setdefault(tuple(bare[j:j + SEED_WORDS]), []).append(j)
    out, i, expect = [], 0, start
    while i < len(said):
        best = (0, 0, 0, [])
        for j in set(seeds.get(tuple(_bare(w) for w in said[i:i + SEED_WORDS]), [])) | {expect}:
            n, m, passed = follow(said[i:], book[j:j + 2 * (len(said) - i) + 8])  # slips never use up more book than this
            if n > best[0] or (n == best[0] and j == expect):
                best = (n, m, j, passed)
        n, m, j, passed = best
        if n >= LEAST:
            out.append({"said": i, "book": j, "words": n, "book_words": m, "passed": len(passed)})
            i, expect = i + n, j + m
        else:
            i += 1
    return out


def marked(generated: str, said: list[re.Match], found: list[dict]) -> list[list[str]]:
    """`generated` cut into [kind, text]: "book" for words in a piece, "own" for the rest.
    The texts join back into `generated`."""
    kinds = ["own"] * len(said)
    for p in found:
        kinds[p["said"]:p["said"] + p["words"]] = ["book"] * p["words"]
    out, last = [], 0
    for i, m in enumerate(said):
        if i + 1 == len(said) or kinds[i + 1] != kinds[i]:  # a stretch ends with this word
            end = len(generated) if i + 1 == len(said) else m.end()
            out.append([kinds[i], generated[last:end]])
            last = end
    return out


def recall(prefix: str, generated: str, book_text: str, next_words: int = 40) -> dict:
    """The recited part of `generated`, what the model wrote after it, what the book says
    there, and the pieces of the book that turn up later in the generation."""
    marks = spans(book_text)
    book = [m.group() for m in marks]
    ends = [m.end() for m in BLOCK.finditer(book_text)]
    at = locate(prefix, book)
    said = spans(generated)
    words = [m.group() for m in said]
    n, m, slips = follow(words, book[at:])
    cut = said[n - 1].end() if n else 0
    after = said[min(n + next_words, len(said)) - 1].end() if n < len(said) else cut

    def block(k: int) -> int:  # 1-based paragraph of the book's k-th word
        return bisect.bisect_right(ends, marks[k].start()) + 1

    given = len(spans(prefix))
    # a model that repeats the words it was given has not recalled anything
    found = [p for p in pieces(words, book, at) if not at - given <= p["book"] < at]
    for p in found:
        p["blocks"] = [block(p["book"]), block(p["book"] + p["book_words"] - 1)]
    return {"words": n,
            "next": generated[cut:after].rstrip(),
            "book": " ".join(book[at + m:at + m + next_words]),
            "passed": [{"at": said[a].start(), "said": " ".join(words[a:b]), "book": " ".join(book[at + c:at + d])}
                       for a, b, c, d in slips],
            "said_words": len(said),
            "book_words": len(book),
            "pieces": found,
            "marked": marked(generated, said, found)}
