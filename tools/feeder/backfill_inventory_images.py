#!/usr/bin/env python3
"""
Match inventory search rows to product photos on disk and emit SQL to add
metadata.image.

Matching rules (deliberately strict — the index once illustrated results with
pictures of the wrong thing):
  1. UPC: digits of the item's upc equal (modulo leading zeros) or contain /
     are contained in a digit run inside the photo filename. Exact, unambiguous.
  2. Name: every meaningful token of the product name appears in the photo
     filename's token set, OR >=85% coverage with >=4 tokens matched.

Usage: python3 backfill_inventory_images.py [--apply]
Reads rows from searchsearcher-postgres via `docker exec ... psql`, photos
from /var/www/html/media. With --apply, pipes UPDATEs into psql.
"""

import json
import re
import subprocess
import sys

MEDIA_DIR = "/var/www/html/media"
MEDIA_BASE = "https://scanner.theofficialblacksheepco.com/media/"
PSQL = ["docker", "exec", "-i", "searchsearcher-postgres",
        "psql", "-U", "searchsearcher", "-d", "searchsearcher", "-t", "-A", "-F", "\t"]

TOKEN_RE = re.compile(r"[a-z0-9]+")
BAD_UPCS = {"", "0", "n/a", "na", "none"}


def run_psql(sql):
    return subprocess.run(PSQL + ["-c", sql], capture_output=True,
                          text=True, check=True).stdout


def norm_digits(s):
    return re.sub(r"\D", "", s or "")


def tokens(s):
    return {t for t in TOKEN_RE.findall((s or "").lower()) if len(t) >= 3}


def filename_tokens(fn):
    # the part before _photo1_ is the product name the uploader gave it
    stem = re.split(r"_photo\d", fn, flags=re.I)[0]
    return tokens(stem.replace("_", " ").replace("-", " "))


def upc_match(upc, fn):
    u = norm_digits(upc).lstrip("0")
    if len(u) < 8:
        return False
    for run in re.findall(r"\d{6,}", fn):
        r = run.lstrip("0")
        if r and (r == u or r in u or u in r):
            return True
    return False


def name_match(name, fn):
    if fn.lower().startswith("unknown_product"):
        return False
    need = tokens(name)
    have = filename_tokens(fn)
    if len(need) < 3:
        return False
    hit = len(need & have)
    return need <= have or (hit >= 4 and hit / len(need) >= 0.85)


def main():
    apply_mode = "--apply" in sys.argv

    photos = sorted(
        fn for fn in subprocess.run(
            ["ls", MEDIA_DIR], capture_output=True, text=True, check=True
        ).stdout.splitlines()
        if re.search(r"_photo\d", fn, re.I)
    )

    out = run_psql(
        "select id, title, source, coalesce(metadata,'{}') "
        "from searchable_items where source like 'inventory:products/%' "
        "order by id"
    )

    updates = []
    for line in out.splitlines():
        if not line.strip():
            continue
        rid, title, source, meta_raw = line.split("\t", 3)
        meta = json.loads(meta_raw)
        if meta.get("image"):
            continue
        upc = str(meta.get("upc") or "")
        # title looks like "BS_00008 — Extra Virgin Olive Oil"
        name = title.split("—", 1)[-1].strip()

        chosen = None
        if upc.lower() not in BAD_UPCS:
            for fn in photos:
                if upc_match(upc, fn):
                    chosen = fn
                    break
        if not chosen:
            for fn in photos:
                if name_match(name, fn):
                    chosen = fn
                    break
        if not chosen:
            continue

        meta["image"] = MEDIA_BASE + chosen
        print(f"{source}: {name}\n    upc={upc} -> {chosen}")
        updates.append((int(rid), json.dumps(meta)))

    print(f"\n{len(updates)} row(s) would gain an image")
    if not apply_mode or not updates:
        return

    stmts = "".join(
        "update searchable_items set metadata = {} where id = {};\n".format(
            "'" + meta.replace("'", "''") + "'", rid)
        for rid, meta in updates
    )
    subprocess.run(
        ["docker", "exec", "-i", "searchsearcher-postgres",
         "psql", "-U", "searchsearcher", "-d", "searchsearcher"],
        input=stmts, text=True, check=True)
    print("applied.")


if __name__ == "__main__":
    main()
