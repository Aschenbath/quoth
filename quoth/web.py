"""How often a passage occurs in an open training corpus, via the infini-gram API.

infini-gram (https://infini-gram.io) indexes trillions of tokens of open
pretraining data and returns exact n-gram counts. For each passage we count its
"seam": the last 5 words of the prefix and the first 5 words of the target,
joined by single spaces. That is the exact transition the model is tested on,
so its count is how many times a model trained on that corpus saw this
prefix lead into this target.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

API = "https://api.infini-gram.io/"
WORD_RE = re.compile(r"\S+")


def crosses_break(passage: dict, before: int = 5, after: int = 5) -> bool:
    """True when the seam spans a line or paragraph break in the text. Copies on the
    web break lines in different places, so an exact count of such a seam says more
    about formatting than about copies; the report leaves these seams out."""
    pre = list(WORD_RE.finditer(passage["prefix"]))[-before:]
    tgt = list(WORD_RE.finditer(passage["target"]))[:after]
    span = passage["prefix"][pre[0].start():] + passage["sep"] + passage["target"][:tgt[-1].end()]
    return "\n" in span


def seam(passage: dict, before: int = 5, after: int = 5) -> str:
    return " ".join(passage["prefix"].split()[-before:] + passage["target"].split()[:after])


def count(query: str, index: str, retries: int = 4) -> int:
    body = json.dumps({"index": index, "query_type": "count", "query": query}).encode()
    for attempt in range(retries):
        req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json",
                                                              "User-Agent": "quoth/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                got = json.load(r)
            if "error" in got:
                raise RuntimeError(got["error"])
            return got["count"]
        except (urllib.error.URLError, TimeoutError, RuntimeError):
            if attempt == retries - 1:
                raise
            time.sleep(10 * (attempt + 1))
    raise AssertionError("unreachable")
