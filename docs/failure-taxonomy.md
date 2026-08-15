# Failure taxonomy

What actually goes wrong when this extractor is run over the eval set, grouped by root cause,
with counts.

This is not a list of things that could go wrong. It was built by reading calls one at a time in
the review surface, writing one free-text note per call with no categories available, and only
then reading all 50 notes back and clustering them. The notes are in `notes/`, so every count
below can be traced to the sentence that produced it.

## Scope, and the caveat that matters

**These counts are one model.** 50 receipts, `claude-haiku-4-5`, run
`run-20260730T092803Z`. The same 50 receipts were also run against Sonnet and Opus, and those
100 calls were not read. Failure rates differ by tier, so nothing here should be quoted as the
system's failure profile. It is Haiku's.

Reading one tier deeply was a deliberate trade. Most of what is counted here is a property of
the receipt rather than the model (whether the OCR is corrupt, whether the address has a
trailing dot), and 50 notes buys either 50 receipts on one model or 17 on three. Full receipt
coverage was worth more. Counting a known mode across all 150 calls is cheap once the checks
are written.

**`date` is excluded from every number below.** The model returns ISO, the labels are
DD/MM/YYYY, so every single call mismatches on format alone. Not one of the 50 notes flagged a
date as actually wrong. All accuracy figures here are over `company`, `address` and `total`.

## The modes

| id | Mode | Calls | Receipts |
|----|------|-------|----------|
| `dropped_trailing_punct` | Dropped a trailing dot or comma the label has | 14 | 000 001 007 010 011 012 014 015 022 029 038 043 046 048 |
| `added_comma` | Added a comma present in neither the OCR nor the label | 13 | 003 008 019 021 025 028 031 032 034 037 039 047 049 |
| `label_spacing` | Label disagrees with the OCR on spacing or punctuation | 12 | 003 005 006 017 018 020 023 024 025 029 047 048 |
| `added_whitespace` | Added whitespace present in neither the OCR nor the label | 9 | 009 010 032 033 035 036 039 044 045 |
| `omitted_chunk` | Cut a field short, dropping a whole line or segment | 8 | 002 004 019 028 040 041 042 049 |
| `dropped_currency` | Dropped the currency symbol from `total` | 7 | 030 032 033 035 036 044 045 |
| `label_character` | Label disagrees with the OCR on a character | 6 | 000 002 013 031 039 045 |
| `appended_extra` | Ran a field long, pulling in OCR text that belongs to no field | 4 | 000 001 005 009 |
| `misread_ocr` | Produced a word the OCR does not contain | 1 | 037 |
| `clean` | Nothing wrong | 3 | 016 026 027 |

Counted per call, not per occurrence. Receipt 039 has four invented commas in one address and
counts once. Per-occurrence counts rank work by how chatty an address is; per-call counts rank
it by how many calls are affected, which is the question a taxonomy exists to answer.

Counts do not sum to 50. A call can carry three modes and several do.

## Three groups, and why the split is the useful part

Not every mode is a failure. Sorting them is what turns a list into a plan.

**Artifact.** A normaliser removes it. The output was correct and the comparison said otherwise.

- `dropped_trailing_punct` (14), `label_spacing` (12), `added_whitespace` (9),
  `dropped_currency` (7)

**Real.** Survives normalisation, and it is the extractor's to fix.

- `added_comma` (13), `omitted_chunk` (8), `appended_extra` (4), `misread_ocr` (1)

**Ceiling.** Survives normalisation, and no prompt change touches it.

- `label_character` (6)

`label_character` is the one to understand before reading any accuracy number from this repo.
The labels were produced by a human reading the receipt image. The extractor is given OCR text.
Where the OCR is corrupt, the label silently fixes it and the model cannot: the OCR says `BND`
and the label says `BHD`, the OCR says `D.T.Y.` and the label says `D.I.Y.`. All six are
confusable glyph pairs. The model copied its input correctly and is marked wrong for it. That
caps the achievable score for reasons that have nothing to do with the model, and it is
invisible unless you read the input alongside the output.

## What the grouping does to the headline

```
exact string match, company + address + total     47 / 50 fail
after the artifact-group normaliser               24 / 50 fail
```

Roughly half of what this harness would report as failure is the ruler, not the model. 23 of 50
calls are correct and were being scored wrong.

`total` is the clearest case. Haiku gets 43 of 50 exactly right and the other 7 differ only by a
leading `$`. Once that is normalised the field is perfect, 50 of 50. Reported as raw equality it
looks like an 86% field.

## The normalisation rules are a decision, not a cleanup

Putting a mode in the artifact group is an assertion that two strings mean the same thing. Those
assertions are not free and they are not obvious.

`added_comma` is the live one. It is the second largest mode and it goes either way:

```
added_comma counted as real       24 / 50 fail    52% pass
added_comma normalised away       17 / 50 fail    66% pass
```

Fourteen accuracy points, decided by answering whether `TAMPOI, 81200` and `TAMPOI 81200` are
the same address. No model, prompt, or data change involved. It is counted as real here, on the
grounds that a normaliser lenient enough to erase a mode is also lenient enough to erase a
regression, and catching regressions is what this harness is for.

This is why the groups are written down and versioned rather than living in a scoring function
nobody reads.

## Two modes that are the same bug

`omitted_chunk` (8) and `appended_extra` (4) are the same field failing in opposite directions.
Eight calls cut `company` or `address` too short, four ran them too long, and `company` fails
both ways. When one field fails in both directions the problem is not model behaviour, it is
that nothing ever defined where a company name ends. `BISTRO & CAFE` on its own line, a
registration number like `(519537-X)`, a proprietor's name above the business name: each is a
judgement call the prompt currently leaves open. That is 12 of the 22 real-group calls, and the
fix is a written definition, not a better model.

## Where the counts came from

Discovery came from the notes. Counts did not, wherever a machine could do better.

`dropped_currency` is the worked example. Five notes mention it. The results file says seven:
035 and 036 were written up as "similar pattern" during a run of near-identical receipts and the
`total` observation was lost in the compression. The notes found the mode. The data counted it.

Any mode a check can detect should be counted from `results/`, and that is the direct handoff
into scoring. `dropped_currency`, `dropped_trailing_punct` and `added_whitespace` are
straightforwardly checkable. `omitted_chunk` and `appended_extra` need a definition of the field
boundary before they can be checked at all, which is a prerequisite, not an implementation
detail.

## Limitations

- **One model.** See the top of this file.
- **The effective sample is smaller than 50.** The 50 receipts are 34 distinct companies and 40
  distinct addresses. One shop appears 7 times and another 5. A failure on a repeated shop is
  counted up to 7 times, so the counts are weighted toward whichever shops repeat, and
  run-to-run variance measured on this set will read tighter than it really is.
- **`date` is untested.** Excluded here for the format reason above, so this taxonomy says
  nothing about whether dates are extracted correctly.
- **The eval set is public.** SROIE is an old dataset and is likely present in training data,
  which pushes the score up. The ceiling group pushes it down. Neither effect is measured.
