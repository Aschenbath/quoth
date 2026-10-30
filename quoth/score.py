"""Teacher-forced recitation scoring.

A passage is a prefix and the target text that really follows it. We run the
model once over prefix + target and, at every target position, ask whether the
model's single most likely next token is the true one.

* The leading run of hits is exactly what greedy decoding (temperature 0) would
  reproduce verbatim from the prefix. Matches after the first miss do not count
  toward it, because greedy decoding would already have left the text.
* Hits anywhere in the target (per word) give a softer picture: which words the
  model "saw coming" given the true text before them. Ordinary prose is partly
  predictable without any memory at all, which is why the corpus also contains
  freshly written control passages that no model can have seen.

Words are whitespace-separated, punctuation included, and a word counts as a
hit only if every token that overlaps it is a hit.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass

import torch

WORD_RE = re.compile(r"\S+")


@dataclass
class Loaded:
    model: torch.nn.Module
    tok: object
    name: str


def load(path: str, dtype: str = "bfloat16", name: str | None = None, mmap: bool = False) -> Loaded:
    """Load a local Hugging Face model. mmap=True maps the weights from disk
    instead of copying them (see mmapload.py)."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(path)
    if mmap:
        from .mmapload import load_mmapped

        model = load_mmapped(path, getattr(torch, dtype))
    else:
        model = AutoModelForCausalLM.from_pretrained(path, dtype=getattr(torch, dtype))
    model.eval()
    return Loaded(model, tok, name or path.rstrip("/\\").replace("\\", "/").split("/")[-1])


def _encode(lm: Loaded, text: str):
    enc = lm.tok(text, return_offsets_mapping=True, add_special_tokens=True)
    ids, offs = enc["input_ids"], [tuple(o) for o in enc["offset_mapping"]]
    # Every model starts from its beginning-of-text token. Gemma's tokenizer adds
    # <bos> itself; OLMo 2's adds nothing, and its <|endoftext|> is the token that
    # precedes each new document in training.
    bos = lm.tok.bos_token_id
    if bos is not None and ids[:1] != [bos]:
        ids, offs = [bos] + ids, [(0, 0)] + offs
    return ids, offs


@torch.inference_mode()
def score(lm: Loaded, prefix: str, sep: str, target: str) -> dict:
    """Score one passage. `sep` is the whitespace that joins prefix and target."""
    text = prefix + sep + target
    start = len(prefix) + len(sep)
    ids, offs = _encode(lm, text)

    # First token past the prefix. Special tokens have empty spans. The separator
    # belongs to the target: a paragraph break must be predicted like a word,
    # because greedy decoding would have to produce it too.
    first = next(i for i, (s, e) in enumerate(offs) if e > s and e > len(prefix))
    n = len(ids)
    k = n - first

    t0 = time.perf_counter()
    out = lm.model(input_ids=torch.tensor([ids]), logits_to_keep=k + 1)
    secs = time.perf_counter() - t0

    logits = out.logits[0, :-1].float()  # predictions for tokens first .. n-1
    tgt = torch.tensor(ids[first:])
    logp = torch.log_softmax(logits, dim=-1).gather(1, tgt[:, None]).squeeze(1)
    hit = (logits.argmax(dim=-1) == tgt).tolist()
    logp = logp.tolist()
    spans = offs[first:]

    words = [(m.start() + start, m.end() + start) for m in WORD_RE.finditer(target)]
    miss = next((j for j, h in enumerate(hit) if not h), None)
    if miss is None:
        greedy_words = len(words)
    else:
        cut = spans[miss][0]
        greedy_words = sum(1 for _, we in words if we <= cut)

    word_hit, word_lp = [], []
    for ws, we in words:
        js = [j for j, (s, e) in enumerate(spans) if s < we and e > ws]
        word_hit.append(int(all(hit[j] for j in js)))
        word_lp.append(round(sum(logp[j] for j in js), 3))

    return {
        "model": lm.name,
        "n_tok": k,
        "n_words": len(words),
        "greedy_tok": k if miss is None else miss,
        "greedy_words": greedy_words,
        "top1_tok": round(sum(hit) / k, 4),
        "top1_words": round(sum(word_hit) / len(words), 4),
        "mean_lp": round(sum(logp) / k, 4),
        "word_hit": "".join(map(str, word_hit)),
        "word_lp": word_lp,
        "secs": round(secs, 3),
    }


@torch.inference_mode()
def generate(lm: Loaded, context: str, max_new_tokens: int) -> str:
    """Greedy continuation of `context` (temperature 0, no sampling)."""
    ids = lm.tok(context, return_tensors="pt", add_special_tokens=True)
    out = lm.model.generate(
        **ids, max_new_tokens=max_new_tokens, do_sample=False, top_p=None, top_k=None
    )
    return lm.tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True)


def leading_word_matches(generated: str, target: str) -> int:
    """How many target words a generated continuation reproduces before diverging."""
    n = 0
    for g, t in zip(WORD_RE.findall(generated), WORD_RE.findall(target)):
        if g != t:
            break
        n += 1
    return n


def bits_per_word(result: dict) -> float:
    """Negative log-likelihood of the target in bits per word (lower = more familiar)."""
    return -sum(result["word_lp"]) / len(result["word_lp"]) / math.log(2)
