# Protocol

Frozen on 2026-10-30, after a pilot and before the main run. The git commit
that adds this file is its timestamp; anything changed later is listed under
"Changes after freezing" at the bottom.

## Question

Which ghost stories can small open-weight language models recite word for word,
and what predicts it: how famous the book is, where in the book the passage
sits, or how often people quote it?

## Corpus

33 public-domain books and stories from Project Gutenberg, chosen by hand before
any scoring, in four tiers (`data/works.json`), plus a fifth tier of controls:

| tier | works | what it is |
|---|---|---|
| canon | 10 | the ghost and horror stories everyone has heard of |
| genre | 8 | well known to readers of the genre |
| forgotten | 9 | Victorian and Edwardian ghost-story writers, mostly women, read by few today |
| late | 6 | Victorian and Edwardian ghost books first released on Gutenberg after January 2025 |
| novel | 16 passages | written for this project on 2026-10-30, never published (`data/controls_novel.txt`) |

* Popularity is Gutenberg's 30-day download count for each book, read on
  2026-10-30 (`downloads` in `works.json`).
* "late" books went online after Gemma 4's training-data cutoff (January 2025,
  per its model card) and after Gemma 3 was released (March 2025). Older scans
  of them may exist elsewhere online, so this tier is "probably unseen", not
  guaranteed. The novel controls are guaranteed unseen.

## Text (`quoth/corpus.py`)

Each Gutenberg file is cut to the text between its START and END markers and to
the narrative itself (from the `start` phrase in `works.json`, skipping title
pages, contents and prefaces). Illustration tags and footnote markers are
removed, underscores (italics) dropped, curly quotes straightened, and prose
paragraphs unwrapped onto one line; verse keeps its line breaks. Small-capital
chapter openings ("MARLEY was dead") are restored to normal case.

## Sampling (`quoth/sample.py`)

Every passage is 40 words of real text (the prefix) and the 50 words that
really follow it (the target). Seed `20261031`. Per work:

* **opening**: the first 90 words of the narrative;
* **body**: one passage per 200 words of text, at most 29 more, one in each of
  equal strata between the opening and the end, starting at a random sentence
  start inside the stratum. Spans containing three or more capitalized words in a
  row (headings) are rejected;
* **quoted**: every level-1 quote of 8 or more words on the English Wikiquote
  pages for the work and its author that can be located in the text
  (`quoth/quotes.py`): the 40 words before the quote are the prefix, the quote
  itself (up to 50 words) is the target. Quotes inside the opening passage, and
  quotes starting within 10 words of one already found, are skipped.

| tier | opening | body | quoted | total |
|---|---|---|---|---|
| canon | 10 | 265 | 87 | 362 |
| genre | 8 | 221 | 12 | 241 |
| forgotten | 9 | 261 | 3 | 273 |
| late | 6 | 173 | 0 | 179 |
| novel | | | | 16 |
| **all** | 33 | 920 | 102 | **1071** |

## Models

Base (pretrained, not instruction-tuned) checkpoints, run locally on a laptop
CPU (Intel Core Ultra 9 285H, 32 GB RAM) in bfloat16:

* `google/gemma-3-1b-pt` (Gemma license)
* `google/gemma-4-E2B` (Apache 2.0)
* `google/gemma-4-E4B` (Apache 2.0)

Gemma 4 is loaded with memory-mapped weights (`quoth/mmapload.py`); scores
match standard loading.

## Measurements (`quoth/score.py`)

One forward pass over prefix + target, with the beginning-of-text token and no
prompt or instructions. At each target token: is the model's top-1 prediction
the true token, and what log-probability did it give the true token?

* `greedy_words`: whole target words before the first miss. This is exactly how
  far greedy decoding (temperature 0) reproduces the text.
* `top1_words`: share of target words whose every token is the top-1
  prediction, given the true text before it. Ordinary prose is partly guessable,
  so this is compared with the novel controls.
* `mean_lp`: mean log-probability per target token.

**Recited** means `greedy_words >= 10`: greedy decoding continues the real text
for at least ten words. In the pilot no novel or late passage passed 4 on any
model.

## Analysis plan

1. Recited passages per model, by tier and kind (opening, body, quoted).
2. Mean `top1_words` per model, tier and kind with 95% bootstrap intervals
   (10,000 resamples, seed `20261031`), against the novel controls.
3. Quoted lines against body passages from the same works.
4. Check: greedy-decode every passage with `greedy_words >= 5` on Gemma 4 E4B,
   plus 60 seeded random others, and compare the decoded run with
   `greedy_words`.
5. Web repetition: for each passage, count the "seam" (the last 5 prefix words
   and first 5 target words, joined by single spaces) in the open DCLM-baseline
   corpus with the infini-gram API (index `v4_dclm-baseline_llama`), and compare
   counts for recited and unrecited passages. DCLM is not Gemma's training data;
   it is an open stand-in for "how often this text is on the web".

## Pilot

Before freezing, 176 passages (all 16 novel controls and body indices 00, 05,
10, 15, 20 of every work, quoted lines not yet included) were scored on all
three models to test the pipeline. They are part of the main sample and are
scored again in the main run. Pilot results (`greedy_words`, max per tier):

| model | canon | genre | forgotten | late | novel |
|---|---|---|---|---|---|
| Gemma 3 1B | 2 | 3 | 3 | 3 | 3 |
| Gemma 4 E2B | 12 | 3 | 3 | 3 | 4 |
| Gemma 4 E4B | 49 | 4 | 2 | 3 | 2 |

What the pilot changed:

* Openings were first prompted with a title-and-author header; the model kept
  writing headers, so openings now use the same 40-word-prefix format as
  everything else.
* Heading filter added; verse detection and small-caps restoration fixed.
* Only openings were recited in the pilot, so the quoted tier was added to test
  whether the lines people repeat are what the model keeps. None of the quoted
  passages were seen in the pilot.

## Changes after freezing

Everything below was decided after the main run had started. The sample, the
metrics and the threshold above did not change.

* **A fourth model, OLMo 2 1B** (`allenai/OLMo-2-0425-1B`, Apache 2.0, from
  ModelScope), added after the three Gemma runs. Its pretraining data is public
  and indexed by infini-gram, so step 5 can count each passage in the data the
  model learned from instead of a stand-in. Same passages, same code.
* **Beginning-of-text token.** OLMo 2's tokenizer adds none, so `score.py` puts
  the tokenizer's `bos_token_id` (`<|endoftext|>` for OLMo 2) in front when the
  tokenizer has not. Gemma's tokenizer already adds `<bos>`, so its scores are
  unaffected.
* **A second corpus in step 5.** Seams are also counted in
  `v4_olmo-mix-1124_llama`, OLMo 2's pretraining data. OLMo 2 is compared with
  its own data, the Gemma models with DCLM.
* **Seams across a line break are left out of step 5** (225 of 1,071 passages,
  `web.crosses_break`). Copies of a text break lines in different places, so the
  exact count of a seam that spans a line or paragraph break measures formatting
  more than copies. This was decided after the counts were in.
* **Step 4, explained.** Generation and the teacher-forced run agree on 77 of 80
  passages. Two of the three that differ are near-ties, where the top two tokens
  are within a few points and bfloat16 breaks the tie differently in one forward
  pass than in step-by-step decoding (`pg932-29`, `pg1065-04`). The third is an
  edition difference (`pg46-00`): the model predicts a paragraph break before
  "Old Marley was as dead as a door-nail", where this edition has none, and
  generation, compared by words, continues all 50. Recited counts use teacher
  forcing, as planned.
* **Reporting.** `python -m quoth report` prints the tables and writes the site's
  `docs/data.json`.
