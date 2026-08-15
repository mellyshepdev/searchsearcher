# tagger

Walks a site directory, derives tags from each page's visible text, and upserts
`<meta name="keywords">` into the HTML.

It lives here because it produces the page keywords searchsearcher is meant to
index — the same tags the hub's `usePageMeta.js` writes for its SPA routes.

## Install

```sh
pip install -r requirements.txt
```

`beautifulsoup4` is the only dependency, and it is the reason this script could
not run where it previously lived.

## Use

```sh
python3 tagger.py /path/to/site --dry-run        # report only, writes nothing
python3 tagger.py /path/to/site                  # apply
python3 tagger.py /path/to/site -t "alpha,beta"  # force these tags on every page
```

Always dry-run first — it prints the tags it would write per file.

## Behaviour

- Tags come from `TAG_RULES` keyword matching against body text. A page's
  `data-tags` / `data-keywords` attribute on `<body>` overrides the heuristic.
- Writes are atomic (tempfile + `fsync` + replace), so an interrupted run
  cannot leave a page half-written.
- Missing `<html>` / `<head>` are synthesised, with `charset="utf-8"` injected.
- `<title>` is preserved.
- Idempotent: a second run over unchanged content reports `No change`.

## Known limitations

**Merging is additive — tags are never removed.** An existing keywords meta is
merged with the new tags (deduped case-insensitively, capped at `--max-len`,
default 1000 chars, then truncated with `…`). So if a page's content changes,
its stale tags persist and re-running cannot clear them. Strip the meta by hand
if a page needs re-tagging from scratch.

**The `release` rule contains a bare `"v"`**, which compiles to `\bv\b` and
matches any standalone "v" in prose. Expect false `release` tags until that
keyword is removed or tightened.

**Static HTML only.** It walks `.html` files on disk, so a client-rendered SPA
exposes nothing but its `index.html`. The hub uses `usePageMeta.js` for that
reason; this tool is for static sites.

## Not wired to searchsearcher yet

Nothing here pushes to `/api/ingest`. The tags land in the HTML only; indexing
them still requires a crawler or a feeder that reads the pages and POSTs them
with `category: "document"`.
