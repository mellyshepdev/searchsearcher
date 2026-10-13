#!/usr/bin/env python3
"""
wallstreet_feeder.py
Push Black Sheep Wall Street's own reports into the searchsearcher index —
one result per report: its headline as the title, excerpt + body as the
content, its art as the picture, and a link to the site.

Reads the same JSON the single-page site renders:
  https://blacksheepwallstreet.com/reports.json        current volume
  https://blacksheepwallstreet.com/archive/vol-N.json  sealed past volumes
The news.json feed is intentionally NOT ingested — those are aggregated
links to outside outlets, not BSWS articles.

Reports render inside the single-page app with no per-article route, so
every result links to the site root. Embargoed reports are skipped until
their embargo date passes.

Usage:
  python3 wallstreet_feeder.py --dry-run
  INGEST_TOKEN=... python3 wallstreet_feeder.py [--api http://host:port]
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

BASE = "https://blacksheepwallstreet.com"
FEEDS = [
    (1, f"{BASE}/archive/vol-1.json"),
    (None, f"{BASE}/reports.json"),  # vol comes from each item, default current
]
DEFAULT_API = "https://search.theofficialblacksheepco.com"
FALLBACK_IMAGE = f"{BASE}/images/w-l.jpeg"


def slug(s: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in (s or "").lower()).strip("-")


def clean_body(body: str) -> str:
    """Strip the light markdown the reader renders so snippets read as prose."""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)          # images
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)        # links -> text
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)          # headings
    t = re.sub(r"^>\s?", "", t, flags=re.M)               # blockquotes
    t = re.sub(r"[*_`]+", "", t)                          # emphasis/code ticks
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def embargoed(r: dict) -> bool:
    e = r.get("embargo")
    if not e:
        return False
    try:
        return datetime.fromisoformat(e.replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except ValueError:
        return False


def build(r: dict, vol: int, server_name: str) -> dict:
    image = r.get("image") or ""
    if image.startswith("/"):
        image = BASE + image
    body = clean_body(r.get("body") or "")
    content = r.get("excerpt") or ""
    if body:
        content = f"{content}\n\n{body}" if content else body
    keywords = ", ".join(dict.fromkeys(x for x in [
        r.get("title"), r.get("section"), r.get("author"),
        f"vol {vol}", "Black Sheep Wall Street", "article", "report"] if x))
    return {
        "serverName": server_name,
        "category": "document",
        "title": r["title"],
        "content": content,
        "keywords": keywords,
        "source": f"bsw-report:vol{vol}:{slug(r['title'])}",
        "tags": ["article", "black-sheep-wall-street", slug(r.get("section", "")), f"vol-{vol}"],
        "status": "active",
        "clearance": 0,
        "metadata": {"url": f"{BASE}/", "image": image or FALLBACK_IMAGE,
                     "slug": r.get("slug", ""), "section": r.get("section", ""),
                     "author": r.get("author", ""), "date": r.get("date", ""),
                     "vol": vol, "site": "blacksheepwallstreet.com"},
    }


def main():
    ap = argparse.ArgumentParser(description="Push Black Sheep Wall Street reports into searchsearcher")
    ap.add_argument("--api", default=os.getenv("SEARCHSEARCHER_URL", DEFAULT_API))
    ap.add_argument("--token", default=os.getenv("INGEST_TOKEN", ""))
    ap.add_argument("--server-name", default="black-sheep-wall-street")
    ap.add_argument("--dry-run", action="store_true", help="Print payloads, send nothing")
    args = ap.parse_args()

    items = []
    for default_vol, url in FEEDS:
        for r in requests.get(url, timeout=30).json():
            if embargoed(r):
                continue
            items.append(build(r, r.get("vol") or default_vol or 1, args.server_name))

    if args.dry_run:
        for it in items:
            m = it["metadata"]
            print(f"--- {it['source']}\n    {it['title']} | {m['section']} | img: {m['image']}")
        print(f"\nDRY RUN — {len(items)} report(s) would be pushed to {args.api}")
        return
    if not args.token:
        raise SystemExit("no ingest token: pass --token or set INGEST_TOKEN")

    ok = failed = 0
    for it in items:
        try:
            r = requests.post(f"{args.api}/api/ingest", json=it, timeout=30,
                              headers={"Authorization": f"Bearer {args.token}",
                                       "X-Ingest-Token": args.token})
            if r.status_code == 200:
                ok += 1
            else:
                failed += 1
                print(f"✗ {it['source']} → {r.status_code} {r.text[:160]}", file=sys.stderr)
        except Exception as e:
            failed += 1
            print(f"✗ {it['source']} → {e}", file=sys.stderr)
    print(f"Pushed {ok} report(s), {failed} failed → {args.api}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
