# quoth

*Quoth the Raven, "Nevermore."*

Which ghost stories can a small open-weight language model recite word for
word? `quoth` feeds Gemma 3 and Gemma 4 the first 40 words of a passage from 33
public-domain ghost stories and checks, token by token, whether the model's top
prediction is the real next word. A model that has memorized a passage
continues it verbatim; a model that hasn't does no better on it than on text
written yesterday.

The method, sample and thresholds were fixed in [PROTOCOL.md](PROTOCOL.md)
before the main run.

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
| `data/works.json` | the 33 works, tiers and Gutenberg download counts |
| `data/controls_novel.txt` | 16 control passages written for this project |
| `data/passages.jsonl` | all 1,071 passages |
| `data/quotes.json` | the Wikiquote lines found in each work |
| `results/` | one JSON line per passage per model |

## Sources and licenses

* Code: MIT ([LICENSE](LICENSE)).
* Texts: public-domain books from [Project Gutenberg](https://www.gutenberg.org).
  The passages are excerpts with the Gutenberg header and footer removed.
* Quote selections: [English Wikiquote](https://en.wikiquote.org), CC BY-SA 4.0.
  The page each quote came from is in `data/quotes.json` (`source`).
* The novel control passages were written by an AI assistant (Claude) for this
  project and are released with the code.
* Models: [Gemma](https://ai.google.dev/gemma) 3 1B (Gemma license) and
  Gemma 4 E2B and E4B (Apache 2.0): the official Google checkpoints, downloaded
  from ModelScope (`LLM-Research/gemma-3-1b-pt`, `google/gemma-4-E2B`,
  `google/gemma-4-E4B`). Not included in this repository.
