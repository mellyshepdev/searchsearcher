#!/usr/bin/env python3
"""
product_feeder.py
Push the store's products into the searchsearcher index, one result per
product: name as the title, its photo as the artwork, and a link straight to
the product page.

Reads the store's public feed (/api/products.json). The bin `location` is
internal and is never indexed. Products ride as category "document" tagged
"product", because public pages (the main site's search bar) show documents
only.

Usage:
  python3 product_feeder.py --dry-run
  INGEST_TOKEN=... python3 product_feeder.py [--api http://host:port]
"""

import argparse
import json
import os
import re
import sys

import requests

STORE = "https://theofficialblacksheepco.store"
DEFAULT_API = "https://search.theofficialblacksheepco.com"
SITE = "theofficialblacksheepco.store"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def money(v) -> str:
    try:
        return f"${float(v):.2f}"
    except (TypeError, ValueError):
        return ""


def build(p: dict) -> dict:
    name = (p.get("name") or "").strip()
    upc = (p.get("upc") or "").strip()
    brand = (p.get("brand") or "").strip()
    cats = [c.strip() for c in (p.get("category") or "").split(",") if c.strip()]
    price = money(p.get("price"))
    url = f"{STORE}/html/product/{upc}/" if upc else STORE
    image = p.get("image") or ""
    if image.startswith("/"):
        image = STORE + image

    lead = " — ".join(x for x in [name, brand, ", ".join(cats), price] if x)
    content = (f"{lead}. In stock at The Official Black Sheep Co. store — "
               f"shop {', '.join(cats) or 'the catalog'} and more.")
    keywords = ", ".join(dict.fromkeys(
        [name, brand, *cats, upc, p.get("bs") or "", "product", "store", "shop", "buy"]))

    return {
        "serverName": SITE,
        "category": "document",
        "title": name,
        "content": content,
        "keywords": keywords,
        "source": f"{SITE}:product/{upc or p.get('id')}",
        "tags": ["product", *[slug(c) for c in cats]],
        "status": "active",
        "clearance": 0,
        "metadata": {"url": url, "site": SITE, "price": price, "brand": brand,
                     "upc": upc, **({"image": image} if image else {})},
    }


def main():
    ap = argparse.ArgumentParser(description="Push store products into searchsearcher")
    ap.add_argument("--feed", default=f"{STORE}/api/products.json")
    ap.add_argument("--api", default=os.getenv("SEARCHSEARCHER_URL", DEFAULT_API))
    ap.add_argument("--token", default=os.getenv("INGEST_TOKEN", ""))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    products = requests.get(args.feed, timeout=30).json()
    items = [build(p) for p in products if p.get("name")]

    if args.dry_run:
        for it in items:
            m = it["metadata"]
            print(f"--- {it['source']}\n    {it['title']} | {m['price']} | {m['url']}\n"
                  f"    image: {m.get('image') or '(none)'}\n    tags: {', '.join(it['tags'])}")
        print(f"\nDRY RUN — {len(items)} product(s) would be pushed to {args.api}")
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
    print(f"Pushed {ok} product(s), {failed} failed → {args.api}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
