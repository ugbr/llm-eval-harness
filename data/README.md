# The eval set

50 scanned receipts and their labels. This is the fixed set every eval run scores against, so it
is committed rather than downloaded: clone the repo, run the harness, get comparable numbers.

## Where it came from

The receipts are from SROIE, the dataset published for the ICDAR 2019 Robust Reading Challenge,
task 3 (key information extraction from scanned receipts).

> Huang, Chen, He, Bai, Karatzas, Lu, Jawahar. *ICDAR2019 Competition on Scanned Receipt OCR and
> Information Extraction.* https://arxiv.org/abs/2103.10213

The full dataset is 1000 receipts. The 50 here are ids `000` through `049`.

## What's in here

`ocr/<id>.csv` is the OCR output for one receipt, copied verbatim from the dataset. One line per
detected text region: eight bounding box coordinates, then the recognized text. The extractor
only reads the text, but the coordinates are kept because the committed data should match the
source and any preprocessing belongs in code where you can see it.

Note that the text itself can contain commas, so a naive `split(",")[8]` truncates it. Rejoin
everything from field 8 onward.

`ground_truth.jsonl` is one row per receipt:

```json
{"id": "000", "company": "BOOK TA .K (TAMAN DAYA) SDN BHD", "address": "NO.53 55,57 & 59, JALAN SAGU 18, TAMAN DAYA, 81100 JOHOR BAHRU, JOHOR.", "date": "25/12/2018", "total": "9.00", "status": "ok", "note": ""}
```

Dates are `DD/MM/YYYY` and totals are decimal strings, both as printed on the receipt. The
extractor emits ISO dates, so scoring normalizes before it compares.

## The labels are hand-verified, and four of them were wrong

Every row was checked against the receipt image by hand. `status` is `ok` for the 46 that matched
the dataset's own label and `fixed` for the 4 that did not, with `note` recording the change:

| id | correction |
|----|------------|
| 024 | address `BEJUNTAL` to `BERJUNTAI` (typo, siblings 023/025 confirm) |
| 026 | company `TED` to `TEO` (typo, siblings 021/023/024/025 confirm) |
| 033 | total empty to `8.20` (Nett Total is printed on the receipt) |
| 039 | company owner entity to the printed trading name `BREWERY TAP` |

This matters more than it looks. Ground truth caps the accuracy any model can score, so a wrong
label reads as a model failure forever. Row 039 also settles a definition the labels have to be
consistent about: `company` is the trading name printed on the receipt, not the owning legal
entity.

## What's deliberately not here

The scanned images. Nothing in the pipeline opens one, the extractor works from OCR text, and
they are about 27MB for these 50.

The dataset's own `key/*.json` labels. `ground_truth.jsonl` supersedes them, and shipping both
would leave two competing sources of truth in one repo with nothing to say which one wins.

## Growing the set

If the set turns out too easy to catch a regression, more receipts are available from the same
source, and expanding is a deliberate call with a stated reason rather than a default. Adding
cases means adding OCR files and hand-verifying labels for them the same way. Do not add a
receipt without a verified label.
