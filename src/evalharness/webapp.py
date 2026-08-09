"""The same review surface as the terminal one, in a browser.

Reading a call means holding three things at once: what the model saw, what it answered, and what
the answer was. A terminal can only stack those vertically, so on a 60 line receipt the OCR text
has scrolled away by the time you reach the fields. Here they sit side by side, and the OCR text
is selectable, which matters more than it sounds: the check that separates "the model got it
wrong" from "the model copied its input correctly and the label came from somewhere richer" is
just looking for the value in the input.

Everything about what a call *is* comes from review.py and everything about storing a note comes
from notes.py, both untouched. This module is a view. That is the whole reason a second surface
was cheap to add, and if a third one ever shows up it should be cheap for the same reason.

Local, single user, no auth, no build step. Do not put this on a network.
"""

from html import escape
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from evalharness import notes, review

# same fixed sentence the terminal surface writes, and it has to stay the same string. the notes
# from both surfaces land in one file and get clustered together at the next step, so two
# spellings of "this one was fine" would read as two different observations.
CLEAN_NOTE = "matches ground truth on all four fields"

# a bare submit is rejected rather than treated as clean, same as the terminal surface. "I read
# this and it was fine" is a real claim about the data, so it gets typed or clicked on purpose.
PROBLEMS = {
    "empty": "say something, or hit the clean button if all four fields matched.",
    "notclean": "not a clean call, some field disagrees. say what you see.",
}


def create_app(
    results_path: Path,
    *,
    models: list[str] | None = None,
    statuses: list[str] | None = None,
    receipts: list[str] | None = None,
    limit: int | None = None,
    notes_dir: Path = notes.NOTES_DIR,
) -> FastAPI:
    """Build the app over one run, with the same filters the terminal surface takes."""
    items = review.load_items(results_path)
    run_id = items[0].row["run_id"]

    if models:
        items = [i for i in items if i.model in set(models)]
    if statuses:
        items = [i for i in items if i.status in set(statuses)]
    if receipts:
        items = [i for i in items if i.receipt_id in set(receipts)]
    if limit:
        items = items[:limit]
    if not items:
        raise SystemExit("no calls match those filters")

    # position in the sorted list, so prev/next follow reading order rather than whatever order
    # the links were clicked in.
    order = {(i.receipt_id, i.model): n for n, i in enumerate(items)}

    app = FastAPI(title="review")

    def noted() -> dict[tuple[str, str, str], notes.Note]:
        # read fresh on every request rather than caching. the file is the source of truth and it
        # is also being appended to by the terminal surface, so a cache here would go stale
        # against a sibling process.
        return notes.current(run_id, notes_dir)

    def find(receipt_id: str, model: str) -> review.ReviewItem:
        for item in items:
            if item.receipt_id == receipt_id and item.model == model:
                return item
        raise KeyError(f"{receipt_id} / {model} is not in this run, or a filter excluded it")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _list_page(items, noted(), run_id, results_path)

    @app.get("/call/{receipt_id}/{model}", response_class=HTMLResponse)
    def detail(receipt_id: str, model: str, err: str = "") -> str:
        item = find(receipt_id, model)
        return _detail_page(item, noted(), order, items, err=PROBLEMS.get(err, ""))

    @app.post("/call/{receipt_id}/{model}")
    def save(
        receipt_id: str,
        model: str,
        text: str = Form(""),
        clean: str = Form(""),
    ) -> RedirectResponse:
        item = find(receipt_id, model)
        text = text.strip()

        # the same guard the terminal surface has. the clean sentence is one click away, so
        # nothing should let that one click record something the page directly contradicts.
        if clean:
            if not _all_match(item):
                return RedirectResponse(
                    f"/call/{receipt_id}/{model}?err=notclean", status_code=303
                )
            text = CLEAN_NOTE

        if not text:
            return RedirectResponse(f"/call/{receipt_id}/{model}?err=empty", status_code=303)

        notes.write(
            run_id=run_id,
            receipt_id=receipt_id,
            model=model,
            text=text,
            notes_dir=notes_dir,
        )
        return RedirectResponse(_next_url(item, noted(), order, items), status_code=303)

    return app


def _all_match(item: review.ReviewItem) -> bool:
    return all(ok for *_, ok in review.compare(item))


def _next_url(
    item: review.ReviewItem,
    done: dict,
    order: dict,
    items: list[review.ReviewItem],
) -> str:
    """The next call still without a note, in reading order. Back to the list when there is none.

    Saving lands you on the next thing to read rather than back on the list, because that is the
    move you make 49 times out of 50. The list is one click away when you want to jump.
    """
    start = order[(item.receipt_id, item.model)]
    for candidate in items[start + 1 :] + items[:start]:
        if candidate.key not in done:
            return f"/call/{candidate.receipt_id}/{candidate.model}"
    return "/"


# ---------------------------------------------------------------------------------------------
# pages. server rendered strings, no template engine and no frontend build. the whole surface is
# three routes and it is read by one person on localhost.
# ---------------------------------------------------------------------------------------------

STYLE = """
:root { color-scheme: light dark; --bg:#fff; --fg:#1a1a1a; --dim:#6b6b6b; --line:#ddd;
        --bad:#b3261e; --good:#146b3a; --panel:#fafafa; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#16181d; --fg:#e6e6e6; --dim:#9aa0a6; --line:#333940;
          --bad:#ff8a80; --good:#7ee2a8; --panel:#1c1f25; }
}
* { box-sizing: border-box; }
body { margin:0; padding:24px; background:var(--bg); color:var(--fg); font:14px/1.5
       ui-sans-serif, system-ui, sans-serif; }
a { color: inherit; }
h1 { font-size:15px; font-weight:600; margin:0 0 16px; }
.dim { color: var(--dim); }
.bar { display:flex; gap:16px; align-items:baseline; margin-bottom:16px; flex-wrap:wrap; }
table { border-collapse: collapse; width:100%; }
th, td { text-align:left; padding:6px 10px; border-bottom:1px solid var(--line);
         vertical-align: top; }
th { font-weight:600; color:var(--dim); font-size:12px; text-transform:uppercase;
     letter-spacing:.04em; }
tr:hover td { background: var(--panel); }
td.note { color: var(--dim); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.flags { font-family: ui-monospace, monospace; letter-spacing:2px; }
.ok { color: var(--good); }
.no { color: var(--bad); }
.split { display:grid; grid-template-columns: 1fr 1fr; gap:24px; align-items:start; }
@media (max-width: 900px) { .split { grid-template-columns: 1fr; } }
.panel { background:var(--panel); border:1px solid var(--line); border-radius:6px; padding:14px; }
pre { margin:0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12.5px;
      white-space: pre-wrap; max-height:70vh; overflow:auto; }
.field { padding:8px 0; border-bottom:1px solid var(--line); }
.field:last-child { border-bottom:0; }
.field .name { font-family: ui-monospace, monospace; font-size:12px; color:var(--dim); }
.val { font-family: ui-monospace, monospace; font-size:12.5px; word-break: break-word; }
.val.t { color: var(--good); }
.val.p { color: var(--bad); }
textarea { width:100%; min-height:80px; padding:10px; font:13px/1.5 ui-sans-serif, system-ui;
           background:var(--bg); color:var(--fg); border:1px solid var(--line); border-radius:6px;
           resize: vertical; }
button { font:13px ui-sans-serif, system-ui; padding:7px 14px; border-radius:6px;
         border:1px solid var(--line); background:var(--panel); color:var(--fg); cursor:pointer; }
button.primary { background:var(--fg); color:var(--bg); border-color:var(--fg); }
.err { color: var(--bad); margin: 8px 0 0; }
"""


def _shell(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(title)}</title><style>{STYLE}</style></head>"
        f"<body>{body}</body></html>"
    )


def _flag(field: str, ok: bool) -> str:
    """One letter per field in the list, coloured by whether it matched."""
    css = "ok" if ok else "no"
    return f"<span class='{css}'>{field[0]}</span>"


def _list_page(
    items: list[review.ReviewItem],
    done: dict,
    run_id: str,
    results_path: Path,
) -> str:
    rows = []
    for item in items:
        note = done.get(item.key)
        flags = "".join(_flag(field, ok) for field, _, _, ok in review.compare(item))
        text = escape(note.text) if note else "<span class='dim'>not read</span>"
        rows.append(
            "<tr>"
            f"<td class='mono'><a href='/call/{item.receipt_id}/{item.model}'>"
            f"{item.receipt_id}</a></td>"
            f"<td class='mono dim'>{escape(item.model)}</td>"
            f"<td class='mono'>{escape(item.status)}</td>"
            f"<td class='flags'>{flags}</td>"
            f"<td class='note'>{text}</td>"
            "</tr>"
        )

    body = (
        f"<h1>{escape(run_id)} <span class='dim'>{len(done)} of {len(items)} read</span></h1>"
        f"<p class='dim'>{escape(results_path.name)}. field letters are company, address, date, "
        "total. green matched the label as a raw string, red did not, and every date is red on "
        "purpose.</p>"
        "<table><tr><th>receipt</th><th>model</th><th>status</th><th>fields</th><th>note</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    return _shell("review", body)


def _detail_page(
    item: review.ReviewItem,
    done: dict,
    order: dict,
    items: list[review.ReviewItem],
    err: str = "",
) -> str:
    note = done.get(item.key)
    matches = _all_match(item)

    fields = []
    for field, truth, predicted, ok in review.compare(item):
        if ok:
            value = f"<div class='val'>{escape(truth)}</div>"
        else:
            shown = "(none)" if predicted is None else predicted
            value = (
                f"<div class='val t'>{escape(truth)}</div>"
                f"<div class='val p'>{escape(shown)}</div>"
            )
        mark = "=" if ok else "!"
        fields.append(f"<div class='field'><div class='name'>{mark} {field}</div>{value}</div>")

    extras = ""
    if item.row.get("error"):
        extras += (
            f"<div class='panel'><b>error</b>"
            f"<pre>{escape(str(item.row['error']))}</pre></div>"
        )
    if item.row.get("prediction") is None and item.row.get("raw_output"):
        extras += (
            f"<div class='panel'><b>raw output</b>"
            f"<pre>{escape(str(item.row['raw_output']))}</pre></div>"
        )

    position = order[(item.receipt_id, item.model)]
    prev_item = items[position - 1] if position else None
    next_item = items[position + 1] if position + 1 < len(items) else None
    nav = " ".join(
        filter(
            None,
            [
                "<a href='/'>list</a>",
                f"<a href='/call/{prev_item.receipt_id}/{prev_item.model}'>prev</a>"
                if prev_item
                else "",
                f"<a href='/call/{next_item.receipt_id}/{next_item.model}'>next</a>"
                if next_item
                else "",
            ],
        )
    )

    url = review.trace_url(item.row.get("trace_id"))
    trace = f"<a href='{escape(url)}'>trace</a>" if url.startswith("http") else f"trace {url}"

    # the clean button only exists on a call that is actually clean, so the one click shortcut
    # cannot record something the page next to it contradicts. the server checks again anyway.
    clean_button = (
        "<button name='clean' value='1' type='submit'>clean</button>" if matches else ""
    )
    already = (
        f"<p class='dim'>already read {escape(note.noted_at)}. saving appends a new note, "
        "the old one stays in the file.</p>"
        if note
        else ""
    )
    problem = f"<p class='err'>{escape(err)}</p>" if err else ""
    existing = escape(note.text) if note else ""

    body = f"""
    <div class='bar'>
      <h1 class='mono'>{escape(item.receipt_id)} &middot; {escape(item.model)}</h1>
      <span class='dim mono'>{escape(item.status)}</span>
      <span class='dim'>{position + 1} of {len(items)}</span>
      <span class='dim'>{len(done)} read</span>
      <span>{nav}</span>
      <span class='dim'>{trace}</span>
    </div>
    <div class='split'>
      <div class='panel'><pre>{escape(item.ocr_text)}</pre></div>
      <div>
        <div class='panel'>{"".join(fields)}</div>
        {extras}
        <form method='post' action='/call/{item.receipt_id}/{item.model}' class='panel'
              style='margin-top:16px'>
          <textarea name='text' autofocus placeholder='what do you see?'
                    >{existing}</textarea>
          {problem}{already}
          <p><button class='primary' type='submit'>save and next</button> {clean_button}
             <span class='dim'>cmd/ctrl + enter</span></p>
        </form>
      </div>
    </div>
    <script>
      document.querySelector('textarea').addEventListener('keydown', function (e) {{
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') e.target.form.requestSubmit();
      }});
    </script>
    """
    return _shell(f"{item.receipt_id} {item.model}", body)
