#!/usr/bin/env python3
"""
ingestor.py
Read a tagger tag file, push the pages it describes into searchsearcher, and
write search_results.json.

The adapter between ser.ops' autoweb.py and this repo's tools. autoweb runs a
two-step pipeline per site and insists on file-in/file-out at each step:

    TAGGER_CMD   <site_dir>   ->  <site_dir>/.tags.json
    INGESTOR_CMD <tag_file>   ->  <site_dir>/search_results.json

site_feeder.py speaks neither end of that — it takes a directory plus a
required --site, POSTs, and writes nothing. This script supplies the contract
and delegates the actual work to site_feeder, so there is one implementation of
what a page means and this stays a shim.

Usage:
  python3 ingestor.py /path/to/site/.tags.json --dry-run
  INGEST_TOKEN=... python3 ingestor.py /path/to/site/.tags.json
"""

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List

import requests

RESULTS_VERSION = 1
DEFAULT_RESULTS = "search_results.json"


def load_site_feeder():
    """Import site_feeder by path, for the same reason it imports the tagger by
    path: tools/feeder is a script directory, not an installable package."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "site_feeder.py")
    if not os.path.exists(path):
        raise SystemExit(f"cannot find site_feeder.py next to {__file__}")
    spec = importlib.util.spec_from_file_location("site_feeder", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load site_feeder from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_tag_file(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        raise SystemExit(f"no tag file at {path} — did the tagger run with --json?")
    except json.JSONDecodeError as e:
        raise SystemExit(f"tag file {path} is not valid JSON: {e}")
    if not isinstance(doc, dict) or "files" not in doc:
        raise SystemExit(f"tag file {path} has no 'files' key; wrong format?")
    return doc


def site_dir_of(doc: dict, tag_file: str) -> str:
    """Where the pages actually live.

    The recorded absolute path wins only if it still exists: autoweb pulls tag
    files back to ./results/<server>/<site>/, where the directory recorded on
    the remote host is meaningless. Falling back to the tag file's own parent
    keeps a pulled-back artifact re-ingestable.
    """
    recorded = doc.get("directory") or ""
    if recorded and os.path.isdir(recorded):
        return recorded
    return os.path.dirname(os.path.abspath(tag_file))


def tags_by_rel(doc: dict) -> Dict[str, List[str]]:
    out = {}
    for entry in doc.get("files") or []:
        rel = (entry.get("path") or "").replace(os.sep, "/")
        if rel:
            out[rel] = [t for t in (entry.get("tags") or []) if t]
    return out


def merge_tagger_tags(items: List[dict], from_file: Dict[str, List[str]]) -> None:
    """Fold the tagger's per-page tags into what site_feeder derived.

    They disagree on purpose. site_feeder reads the <head> and demands
    --min-hits distinct keywords before it grants a tag; the tagger matches a
    single keyword against body text, and also honours a page's explicit
    `data-tags` attribute, which site_feeder ignores entirely. That attribute is
    the one case where the page author knows better than either heuristic, so
    the union is what should be indexed.

    Merged-in tags reach `keywords` (weight D) but never the synonym expansion,
    which is gated on hit counts they do not have. A hand-tagged page therefore
    becomes findable by its own tag without dragging a rule's whole vocabulary
    in behind it.
    """
    for it in items:
        rel = (it.get("metadata") or {}).get("path", "").replace(os.sep, "/")
        extra = [t for t in from_file.get(rel, []) if t not in it["tags"]]
        if not extra:
            continue
        it["tags"] = it["tags"] + extra
        it["keywords"] = ", ".join(
            [p for p in [it["keywords"], ", ".join(extra)] if p])


def main():
    ap = argparse.ArgumentParser(
        description="Push the pages named by a tagger tag file into searchsearcher")
    ap.add_argument("tag_file", help="Path to .tags.json, as written by tagger.py --json")
    ap.add_argument("--out", help=f"Where to write results (default: <site_dir>/{DEFAULT_RESULTS})")
    ap.add_argument("--site", default="", help="Override the site name from the tag file")
    ap.add_argument("--base-url", default="", help="Override the base URL from the tag file")
    ap.add_argument("--base-url-template", default="",
                    help="Derive the base URL from the site name, e.g. 'https://{site}/'")
    ap.add_argument("--api", default=os.getenv("SEARCHSEARCHER_URL", ""))
    ap.add_argument("--token", default=os.getenv("INGEST_TOKEN", ""))
    ap.add_argument("--server-name", default="", help="Which 'server' pages are attributed to")
    ap.add_argument("--min-hits", type=int, default=2)
    ap.add_argument("--synonym-min-hits", type=int, default=3)
    ap.add_argument("--no-synonyms", action="store_true")
    ap.add_argument("--no-tagger-tags", action="store_true",
                    help="Ignore the tag file's tags; derive everything from page text")
    ap.add_argument("--clearance", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="Collect and write results, send nothing")
    args = ap.parse_args()

    sf = load_site_feeder()
    api = args.api or sf.DEFAULT_API
    doc = read_tag_file(args.tag_file)
    directory = site_dir_of(doc, args.tag_file)
    site = args.site or doc.get("site") or os.path.basename(os.path.abspath(directory))
    base_url = args.base_url or doc.get("base_url") or ""
    if not base_url and args.base_url_template:
        base_url = args.base_url_template.format(site=site)
    # autoweb names its servers srv-03..srv-09; falling back to the site keeps
    # the (server, source, title) upsert key unique when it does not pass one.
    server_name = args.server_name or site

    out_path = args.out or os.path.join(directory, DEFAULT_RESULTS)

    items = sf.collect(directory, sf.load_tag_rules(), site, base_url,
                       server_name, not args.no_synonyms, args.min_hits,
                       args.synonym_min_hits, args.clearance)
    if not args.no_tagger_tags:
        merge_tagger_tags(items, tags_by_rel(doc))

    results = []
    ok = failed = 0
    for it in items:
        row = {
            "source": it["source"],
            "title": it["title"],
            "url": it["metadata"].get("url", ""),
            "path": it["metadata"].get("path", ""),
            "tags": it["tags"],
        }
        if args.dry_run:
            row["status"] = "dry-run"
        else:
            try:
                r = requests.post(f"{api}/api/ingest", json=it, timeout=30,
                                  headers={"Authorization": f"Bearer {args.token}"})
                row["http_status"] = r.status_code
                if r.status_code == 200:
                    ok += 1
                    row["status"] = "ok"
                    try:
                        row["response"] = r.json()
                    except ValueError:
                        row["response"] = r.text[:200]
                    print(f"✓ {it['source']}")
                else:
                    failed += 1
                    row["status"] = "failed"
                    row["error"] = r.text[:200]
                    print(f"✗ {it['source']} → {r.status_code} {r.text[:160]}", file=sys.stderr)
            except Exception as e:
                failed += 1
                row["status"] = "failed"
                row["error"] = str(e)
                print(f"✗ {it['source']} → {e}", file=sys.stderr)
        results.append(row)

    if not args.dry_run and not args.token and items:
        # Every POST above already failed on a missing bearer; say why once.
        print("no ingest token: pass --token or set INGEST_TOKEN", file=sys.stderr)

    doc_out = {
        "version": RESULTS_VERSION,
        "generated": datetime.now(timezone.utc).isoformat(),
        "site": site,
        "directory": os.path.abspath(directory),
        "tag_file": os.path.abspath(args.tag_file),
        "api": api,
        "base_url": base_url,
        "server_name": server_name,
        "dry_run": args.dry_run,
        "counts": {"collected": len(items), "ok": ok, "failed": failed},
        "results": results,
    }
    # Written even when every page failed: autoweb pulls this artifact back as
    # the record of the run, and an absent file is indistinguishable from a
    # crash before the first POST.
    sf_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(sf_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc_out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    verb = "would push" if args.dry_run else "pushed"
    print(f"\n{verb} {len(items) if args.dry_run else ok} page(s), "
          f"{failed} failed → {api}")
    print(f"Wrote {out_path}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
