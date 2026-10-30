# quoth

*Quoth the Raven, "Nevermore."*

Which ghost stories can a small open-weight language model recite word for
word? `quoth` feeds Gemma 3, Gemma 4 and OLMo 2 the first 40 words of a passage
from 33 public-domain ghost stories and checks, token by token, whether the
model's top prediction is the real next word. A model that has memorized a
passage continues it verbatim; a model that hasn't does no better on it than on
text written yesterday.

The method, sample and thresholds were fixed in [PROTOCOL.md](PROTOCOL.md)
before the main run; what changed afterwards is listed at its end. Read along
with the models on the [site](https://aschenbath.github.io/quoth/) (`docs/`).

## Results

A passage is **recited** when greedy decoding continues the real text for ten
words or more. Passages recited, out of 1,071:

| model | openings (33) | random pages (920) | quoted lines (102) | written yesterday (16) |
|---|---|---|---|---|
| Gemma 3 1B | 0 | 0 | 0 | 0 |
| OLMo 2 1B | 1 | 0 | 1 | 0 |
| Gemma 4 E2B | 1 | 2 | 2 | 0 |
| Gemma 4 E4B | 3 | 4 | 3 | 0 |

* Every recited passage comes from four of the ten canon works: Jekyll and Hyde,
  A Christmas Carol, The Fall of the House of Usher and The Raven. No model
  recites anything from the 15 forgotten or newly posted books; the longest run on
  them is five words.
* In the canon, Gemma 4 E4B predicts 73% of the words of openings [58-87] and 57%
  of quoted lines [51-62], against 39% [37-40] on random pages and 37% [33-41] on
  control passages written yesterday.
* Copies help a little but don't decide it. Random pages whose seam occurs 100
  times or more in OLMo 2's own pretraining data: 139, of which OLMo 2 1B recites
  none, with a longest run of six words. In DCLM: 138, of which Gemma 4 E4B
  recites three.

Limits: the control passages were written by an AI, and such text is easier for a
model to predict, so they are a generous baseline; random pages from the forgotten
books (33%) and from books posted after training (34%) land a little below them.
The "late" books are probably unseen, not certainly. Copies are exact matches in
deduplicated corpora, so they undercount the web, and DCLM is only a stand-in for
Gemma's private training data. Prediction is measured on a sample of pages, not
on whole books, so "recites none" means none of the sampled passages.

Read loosely, the counts are a floor. Given the first 40 words of The Raven,
Gemma 4 E4B writes the next 709 words of the poem, with 2 differences from the
1845 text, though the strict test scores that passage 2 because of a curly
quotation mark. `quoth/recall.py` is that looser ruler; it was added after the
main run and is kept apart from the counts above.

## Reproduce

Python 3.13, CPU only. About 10 GB of free RAM is enough for Gemma 4 E4B with
`--mmap`.

```sh
pip install -r requirements.txt
pip install -e .   # or put this folder on PYTHONPATH

# 1. texts and passages (downloads 33 books from Project Gutenberg)
python -m quoth quotes --wikiquote WIKIQUOTE_DIR --cache GUTENBERG_DIR
python -m quoth sample --cache GUTENBERG_DIR

# 2. score with any local Hugging Face causal LM
python -m quoth score --model models/gemma-4-E4B --mmap --out results/gemma-4-E4B.jsonl

# 3. greedy decoding check
python -m quoth generate --model models/gemma-4-E4B --mmap \
    --scores results/gemma-4-E4B.jsonl --out results/gemma-4-E4B.gen.jsonl

# 4. copies of each passage's seam in open corpora (infini-gram API)
python -m quoth web --index v4_dclm-baseline_llama --out results/web-dclm.jsonl
python -m quoth web --index v4_olmo-mix-1124_llama --out results/web-olmo-mix.jsonl

# 5. tables, and the site's data
python -m quoth report --site docs/data.json

# 6. long generations, read with the looser ruler
python -m quoth generate --model models/gemma-4-E4B --mmap --ids ID,ID,...     --max-new 400 --out results/gemma-4-E4B.long.jsonl
python -m quoth recall --gen results/gemma-4-E4B.long.jsonl --cache GUTENBERG_DIR     --out results/gemma-4-E4B.recall.jsonl
python -m quoth recall --gen results/gemma-4-E4B.raven.jsonl --book data/raven-1845.txt     --out results/gemma-4-E4B.raven-1845.jsonl

# probe any text file of your own
python -m quoth recite --model models/gemma-3-1b-pt --text some_book.txt
```

`data/passages.jsonl` is already built, so step 1 is only needed to check it.

## Files

| path | what |
|---|---|
| `quoth/corpus.py` | Gutenberg download and text normalization |
| `quoth/sample.py` | the seeded passage sample |
| `quoth/quotes.py` | Wikiquote lines located in the texts |
| `quoth/score.py` | teacher-forced scoring and greedy decoding |
| `quoth/mmapload.py` | memory-mapped loading of safetensors checkpoints |
| `quoth/web.py` | counts of a passage's seam in open corpora, via infini-gram |
| `quoth/recall.py` | the looser ruler for long generations (not a frozen measure) |
| `quoth/report.py` | the tables and the site's `data.json` |
| `docs/` | the site (plain HTML, CSS and JS, served by GitHub Pages) |
| `data/works.json` | the 33 works, tiers and Gutenberg download counts |
| `data/controls_novel.txt` | 16 control passages written for this project |
| `data/raven-1845.txt` | The Raven, 1845 text, from the Poetry Foundation's page |
| `data/passages.jsonl` | all 1,071 passages |
| `data/quotes.json` | the Wikiquote lines found in each work |
| `results/` | one JSON line per passage per model, and the corpus counts |

## Sources and licenses

* Code: MIT ([LICENSE](LICENSE)).
* Texts: public-domain books from [Project Gutenberg](https://www.gutenberg.org).
  The passages are excerpts with the Gutenberg header and footer removed.
* The Raven (`data/raven-1845.txt`): public domain, first published by Wiley and
  Putnam, 1845; text as given by the [Poetry Foundation](https://www.poetryfoundation.org/poems/48860/the-raven).
* Quote selections: [English Wikiquote](https://en.wikiquote.org), CC BY-SA 4.0.
  The page each quote came from is in `data/quotes.json` (`source`).
* The novel control passages were written by an AI assistant (Claude) for this
  project and are released with the code.
* Models: [Gemma](https://ai.google.dev/gemma) 3 1B (Gemma license) and
  Gemma 4 E2B and E4B (Apache 2.0): the official Google checkpoints, downloaded
  from ModelScope (`LLM-Research/gemma-3-1b-pt`, `google/gemma-4-E2B`,
  `google/gemma-4-E4B`). [OLMo 2](https://allenai.org/olmo) 1B (Apache 2.0) from
  Ai2, also from ModelScope (`allenai/OLMo-2-0425-1B`). Not included in this
  repository.
* Corpus counts: the [infini-gram](https://infini-gram.io) API, over DCLM-baseline
  and OLMo 2's pretraining data (OLMo-mix-1124).
* Built with [Claude Code](https://claude.com/claude-code), an AI coding agent,
  which wrote most of the code and text with the author.
