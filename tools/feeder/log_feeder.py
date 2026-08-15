#!/usr/bin/env python3
"""
log_feeder.py
Push notable live-logger entries into the searchsearcher index as patterns.

Deliberately not a log shipper. live-logger already stores raw history (~115k
rows/day, 284MB, with hourly rollover on unit7) and searchsearcher has no
retention at all — copying rows across would build an unbounded third copy of
the log store.

Instead this indexes *what is going wrong*: ERROR/WARN lines normalised into
patterns, deduped, with an occurrence count. 15,829 raw rows collapse to a few
hundred patterns, which is the part a human would actually search for.

Usage:
  python3 log_feeder.py --dry-run
  python3 log_feeder.py --since 24 --limit 200 --token "$INGEST_TOKEN"
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import psycopg2
import requests

DEFAULT_API = "https://search.theofficialblacksheepco.com"
NOTABLE = ("ERROR", "WARN")

# Variable parts of a message, replaced so that a thousand near-identical lines
# collapse to the one pattern worth reading. Order matters: longest first.
# Traefik and systemd colourise their output; the escape codes survive into the
# DB and both uglify the pattern and break the timestamp regex below.
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\[\d{1,2}m")

NOISE = [
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<ts>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<ip>"),
    (re.compile(r"\b[0-9a-fA-F]{12,}\b"), "<hash>"),
    (re.compile(r"\b\d{2}:\d{2}:\d{2}\b"), "<time>"),
    (re.compile(r"/[^\s\"]*\b\d+\b[^\s\"]*"), "<path>"),
    (re.compile(r"\b\d+(?:\.\d+)?(?:ms|s|kb|mb|gb|%)\b", re.I), "<qty>"),
    (re.compile(r"\b\d+\b"), "<n>"),
]


def normalise(msg: str) -> str:
    out = ANSI.sub("", msg).strip()
    for pattern, repl in NOISE:
        out = pattern.sub(repl, out)
    return re.sub(r"\s+", " ", out).strip()


def fetch(dsn: str, since_hours: int, max_rows: int):
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    with psycopg2.connect(dsn, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT unit, container, level, message, event_time
                  FROM logs
                 WHERE level = ANY(%s) AND event_time >= %s
                 ORDER BY event_time DESC
                 LIMIT %s
                """,
                (list(NOTABLE), since, max_rows),
            )
            return cur.fetchall()


def group(rows):
    """Collapse rows into (unit, container, level, pattern) buckets."""
    buckets = defaultdict(lambda: {"count": 0, "first": None, "last": None, "example": ""})
    for unit, container, level, message, event_time in rows:
        pattern = normalise(message or "")
        if not pattern:
            continue
        key = (unit or "unknown", container or "unknown", level or "ERROR", pattern[:400])
        b = buckets[key]
        b["count"] += 1
        if b["first"] is None or event_time < b["first"]:
            b["first"] = event_time
        if b["last"] is None or event_time > b["last"]:
            b["last"] = event_time
        if not b["example"]:
            b["example"] = (message or "").strip()[:1500]
    return buckets


def to_items(buckets, limit):
    ranked = sorted(buckets.items(), key=lambda kv: -kv[1]["count"])[:limit]
    items = []
    for (unit, container, level, pattern), b in ranked:
        items.append({
            "serverName": unit,
            "category": "log",
            # The pattern is the title: it is the thing a human recognises and
            # searches for, and it keeps the (server, source, title) upsert
            # stable so re-runs refresh counts instead of duplicating.
            "title": pattern[:400],
            "content": (
                f"{b['count']} occurrence(s) on {unit}/{container} "
                f"between {b['first']} and {b['last']}.\n\n"
                f"Example: {b['example']}"
            ),
            "keywords": ", ".join([unit, container, level, "log", "error" if level == "ERROR" else "warning"]),
            "source": f"live-logger:{container}",
            "tags": [level.lower(), container, unit],
            "status": "error" if level == "ERROR" else "warning",
            "severity": level,
            "metadata": {
                "unit": unit,
                "container": container,
                "level": level,
                "count": b["count"],
                "first_seen": b["first"].isoformat() if b["first"] else None,
                "last_seen": b["last"].isoformat() if b["last"] else None,
            },
        })
    return items


def main():
    ap = argparse.ArgumentParser(description="Index notable live-logger patterns")
    ap.add_argument("--dsn", default=os.getenv("LIVE_LOGGER_DATABASE_URL", ""),
                    help="live-logger Postgres DSN")
    ap.add_argument("--since", type=int, default=24, help="Lookback window in hours")
    ap.add_argument("--max-rows", type=int, default=50000, help="Row cap per run")
    ap.add_argument("--limit", type=int, default=200, help="Top N patterns to push")
    ap.add_argument("--api", default=os.getenv("SEARCHSEARCHER_URL", DEFAULT_API))
    ap.add_argument("--token", default=os.getenv("INGEST_TOKEN", ""))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.dsn:
        raise SystemExit("no DSN: pass --dsn or set LIVE_LOGGER_DATABASE_URL")

    rows = fetch(args.dsn, args.since, args.max_rows)
    buckets = group(rows)
    items = to_items(buckets, args.limit)
    print(f"{len(rows)} rows → {len(buckets)} patterns → pushing {len(items)}")

    if args.dry_run:
        for it in items[:15]:
            m = it["metadata"]
            print(f"  [{m['count']:>5}x] {m['unit']}/{m['container']} {m['level']}: {it['title'][:90]}")
        print(f"\nDRY RUN — nothing sent to {args.api}")
        return

    if not args.token:
        raise SystemExit("no ingest token: pass --token or set INGEST_TOKEN")

    ok = failed = 0
    for it in items:
        try:
            r = requests.post(f"{args.api}/api/ingest", json=it, timeout=30,
                              headers={"Authorization": f"Bearer {args.token}"})
            if r.status_code == 200:
                ok += 1
            else:
                failed += 1
                print(f"✗ {it['title'][:60]} → {r.status_code} {r.text[:120]}", file=sys.stderr)
        except Exception as e:
            failed += 1
            print(f"✗ {it['title'][:60]} → {e}", file=sys.stderr)
    print(f"Pushed {ok} pattern(s), {failed} failed → {args.api}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
