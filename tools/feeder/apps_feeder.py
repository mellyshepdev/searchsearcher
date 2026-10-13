#!/usr/bin/env python3
"""Push the ecosystem's apps into searchsearcher as public results.

Apps are single-page or sign-in-gated, so site_feeder has nothing to crawl:
each one is described here by hand. Re-run after editing APPS; ingest upserts
by `source`, so re-runs update rather than duplicate.

  python tools/feeder/apps_feeder.py --api http://100.123.158.58:8219   (INGEST_TOKEN in env)
"""
import argparse
import os
import sys

import requests

DEFAULT_API = "http://100.123.158.58:8219"

APPS = [
    {
        "id": "nasa-calendar",
        "site": "nasa.theofficialblacksheepco.online",
        "title": "NASA Calendar — 3D Space Calendar",
        "url": "https://nasa.theofficialblacksheepco.online/",
        "image": "https://nasa.theofficialblacksheepco.online/deepspace-sheep-icon.png",
        "content": ("An interactive 3D calendar set in deep space: each day is a cube among NASA "
                    "spacecraft, the Moon, comets and the Curiosity rover. Connect your Google "
                    "Calendar or your Reech calendar and your events and Google Meet links appear "
                    "on their days. Move month to month to plan ahead."),
        "keywords": "calendar, nasa, nasa calendar, nasa-project, space calendar, 3d calendar, "
                    "google calendar, reech calendar, events, schedule, planner, meet",
        "tags": ["app", "calendar", "nasa"],
    },
    {
        "id": "reech-calendar",
        "site": "reech.prime-quality.online",
        "title": "Reech — Calendar & Communications Hub",
        "url": "https://reech.prime-quality.online/",
        "content": ("Reech is the Black Sheep communications hub: your calendar, email (any number "
                    "of mailboxes), Matrix messaging, Pushbullet and contacts in one inbox. Connect "
                    "Google in Reech or in the portal's Settings and your Google Calendar events "
                    "and Meet links show up in the Reech calendar, and in the NASA calendar too."),
        "keywords": "reech, reech calendar, calendar, google calendar, google meet, email, inbox, "
                    "matrix, messaging, pushbullet, contacts, communications, schedule, events",
        "tags": ["app", "calendar", "communications"],
    },
]


def build(a: dict) -> dict:
    meta = {"url": a["url"], "site": a["site"]}
    if a.get("image"):
        meta["image"] = a["image"]
    return {
        "serverName": a["site"],
        "category": "document",
        "title": a["title"],
        "content": a["content"],
        "keywords": a["keywords"],
        "source": f"apps:{a['id']}",
        "tags": a["tags"],
        "status": "active",
        "clearance": 0,
        "metadata": meta,
    }


def main():
    ap = argparse.ArgumentParser(description="Push ecosystem apps into searchsearcher")
    ap.add_argument("--api", default=os.getenv("SEARCHSEARCHER_URL", DEFAULT_API))
    ap.add_argument("--token", default=os.getenv("INGEST_TOKEN", ""))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    items = [build(a) for a in APPS]
    if args.dry_run:
        for it in items:
            print(f"--- {it['source']}: {it['title']} -> {it['metadata']['url']}")
        return
    if not args.token:
        raise SystemExit("no ingest token: pass --token or set INGEST_TOKEN")
    failed = 0
    for it in items:
        r = requests.post(f"{args.api}/api/ingest", json=it, timeout=30,
                          headers={"Authorization": f"Bearer {args.token}", "X-Ingest-Token": args.token})
        print(f"{'✓' if r.status_code == 200 else '✗'} {it['source']} → {r.status_code}")
        failed += r.status_code != 200
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
