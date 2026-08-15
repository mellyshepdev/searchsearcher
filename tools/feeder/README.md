# site_feeder

Walks a site directory, tags each page, and pushes it into the searchsearcher
index via `POST /api/ingest`.

The tagger writes keywords *into* HTML. This reads pages and makes them
searchable. Together they close the loop: tagged pages actually turn up in
results.

## Install

```sh
pip install -r requirements.txt
```

## Use

```sh
# Always look first
python3 site_feeder.py /path/to/site --site diesel.tech \
    --base-url https://gbonds1.gitlab.io/diesel.tech --dry-run

# Then push
export INGEST_TOKEN=...        # same token the app runs with
python3 site_feeder.py /path/to/site --site diesel.tech \
    --base-url https://gbonds1.gitlab.io/diesel.tech
```

Options: `--api` (defaults to the public URL, or `$SEARCHSEARCHER_URL`),
`--server-name` (which "server" pages are attributed to, default
`gitlab-pages`), `--no-synonyms`, `--dry-run`.

## Two design decisions that matter

**It reads the `<head>`, not just the body.** The tagger matches on body text,
which is empty on a client-rendered SPA — diesel.tech's pages are Vite shells
whose entire meaning lives in `<title>`, `description` and the `og:` tags.
Body-only extraction would have indexed them as blank.

**Matched tags are expanded back into their rule vocabulary.** searchsearcher's
full-text vector covers title (weight A) and content (weight B) only — the
`tags[]` column is stored but never searched. So a tag alone is invisible to
search, and anything findable has to reach the content field.

This is what makes the headline case work. The Volvo D13 page never says
"truck" — not in its title, description, or keywords. But it matches the
`diesel` rule, whose vocabulary is
`fuel, engine, diesel, vehicle, tech, truck, wheeler, semi`, so those land in a
`Related:` line and searching **trucks** finds the diesel trainer.

Verified against the live index:

| query | result |
|---|---|
| `trucks` | Volvo D13 Engine – Interactive 3D Viewer |
| `semi`, `wheeler`, `mechanic` | same page |
| `diesel` | same page, rank 2.0 (its own text, not a synonym) |

Turn it off with `--no-synonyms` if a site should only match its own words.

## Known limitations

- **Bare digits are dropped** from synonym expansion (the `diesel` rule's
  `"18"`), so `18 wheeler` finds nothing while `wheeler` works. Query terms are
  AND-joined, so the unmatched `18` kills the whole query.
- **Pages with no description and under 40 chars of body are skipped.** Their
  content would be nothing but inferred tags, which indexes a near-duplicate of
  whatever richer page shares their title.
- **Upsert key is `(server, source, title)`** and `source` is
  `<site>:<relative/path>`, so re-running updates pages in place rather than
  duplicating. Safe to run on a schedule.
- **No deletion.** A page removed from the site stays in the index.
