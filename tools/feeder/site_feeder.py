#!/usr/bin/env python3
"""
site_feeder.py
Walk a site directory, tag each page, and push it into the searchsearcher index.

The companion to tools/tagger. The tagger writes keywords *into* the HTML;
this reads pages and POSTs them to /api/ingest so they become searchable.

Usage:
  python3 site_feeder.py /path/to/site --site diesel.tech \
      --base-url https://gbonds1.gitlab.io/diesel.tech --dry-run
  python3 site_feeder.py /path/to/site --site diesel.tech --token "$INGEST_TOKEN"
"""

import argparse
import importlib.util
import json
import os
import re
import sys
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

DEFAULT_API = "https://search.theofficialblacksheepco.com"

# Keycloak's silent-SSO iframes and other machinery are not content.
SKIP_NAMES = {"silent-check-sso.html", "404.html", "200.html"}


def load_tag_rules() -> Dict[str, List[str]]:
    """Borrow the tagger's vocabulary so both tools agree on what a tag means.

    Imported by path rather than as a package: tools/tagger is a plain script
    directory, not an installable module.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    # Two layouts have to work: this repo (tools/feeder + tools/tagger) and the
    # flat one autoweb.py deploys to, where every script lands in ~/tools/.
    candidates = [
        os.path.join(here, "..", "tagger", "tagger.py"),
        os.path.join(here, "tagger.py"),
    ]
    tagger_path = next((c for c in candidates if os.path.exists(c)), None)
    if tagger_path is None:
        raise SystemExit("cannot find tagger.py; looked in " +
                         ", ".join(os.path.normpath(c) for c in candidates))
    spec = importlib.util.spec_from_file_location("tagger", tagger_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load tagger from {tagger_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.TAG_RULES


# Site-wide chrome. Present verbatim on every page, so anything read out of it
# describes the site, not the page — and it poisons everything downstream:
# the nav strip "Tech-Sector Cleaning Services Pet Services Junk Removal" got
# the bible-study page tagged `diesel` (so it ranked for "diesel" searches) and
# made the main site's image picker match /pet/ on literally every result.
CHROME_SELECTORS = ("nav", "header", "footer", "script", "style", "noscript",
                    "svg", "template")
CHROME_CLASS_RE = re.compile(
    r"(^|[\s_-])(nav|navbar|menu|header|footer|sidebar|breadcrumb|cookie|banner)"
    r"([\s_-]|$)", re.I)


def strip_chrome(soup: BeautifulSoup) -> None:
    """Drop navigation and boilerplate before any text is read from the page."""
    for tag in soup.find_all(CHROME_SELECTORS):
        tag.decompose()
    for tag in soup.find_all(attrs={"class": CHROME_CLASS_RE}):
        tag.decompose()
    for tag in soup.find_all(attrs={"id": CHROME_CLASS_RE}):
        tag.decompose()
    for tag in soup.find_all(attrs={"role": re.compile(
            r"^(navigation|banner|contentinfo)$", re.I)}):
        tag.decompose()


def page_text(soup: BeautifulSoup) -> Dict[str, str]:
    """Everything worth indexing on a page.

    Deliberately reads the <head> as well as the body. The tagger only looks at
    body text, which is empty on a client-rendered SPA — diesel.tech's pages are
    Vite shells whose entire meaning lives in <title>, description and og: tags.
    Body-only extraction would index them as blank.
    """
    def meta(*names):
        for n in names:
            el = soup.find("meta", attrs={"name": n}) or soup.find("meta", attrs={"property": n})
            if el and el.get("content"):
                return el["content"].strip()
        return ""

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    title = title or meta("og:title", "twitter:title")

    image = meta("og:image", "twitter:image")

    strip_chrome(soup)
    body = soup.body.get_text(" ", strip=True) if soup.body else ""
    return {
        "title": title,
        "description": meta("description", "og:description", "twitter:description"),
        "keywords": meta("keywords"),
        "image": image,
        "body": re.sub(r"\s+", " ", body).strip(),
    }


def tag_hits(parts: Dict[str, str], rules: Dict[str, List[str]]) -> Dict[str, int]:
    """How many *distinct* keywords of each rule the page matches.

    Counting distinct keywords rather than testing "any keyword matched" is what
    keeps the vocabulary honest. Several rules share weak words — `diesel`
    contains "tech" and "vehicle" — so a single hit means almost nothing. On the
    real sites, one-hit matching tagged a commercial cleaning page as `diesel`
    and `training`, which would then have injected truck synonyms into it and
    polluted every truck search.
    """
    haystack = " ".join([parts["title"], parts["description"],
                         parts["keywords"], parts["body"]]).lower()
    if not haystack.strip():
        return {}
    hits: Dict[str, int] = {}
    for tag, words in rules.items():
        n = 0
        for w in words:
            if re.search(r"\b" + re.escape(w) + r"\b", haystack, re.IGNORECASE):
                n += 1
        if n:
            hits[tag] = n
    return hits


def build_content(parts: Dict[str, str]) -> str:
    """The page's own prose. Indexed at weight 'B'."""
    chunks = []
    if parts["description"]:
        chunks.append(parts["description"])
    if parts["body"]:
        chunks.append(parts["body"][:4000])
    return "\n\n".join(chunks)


def site_terms(site: str, base_url: str) -> List[str]:
    """The site's own name, in the forms someone would actually type.

    Without this a site is unfindable by its own name: `site` only ever reached
    `metadata`, which is a plain text column and not part of the search vector,
    so "diesel.tech" matched nothing while the page it should have returned sat
    in the index. Both the dotted name and its parts are emitted, because
    to_tsquery('english') lexes "diesel.tech" as a single host token — a page
    carrying only the word "diesel" is not a match for it, and vice versa.
    """
    terms, seen = [], set()
    candidates = [site]
    if base_url:
        host = re.sub(r"^https?://", "", base_url).split("/")[0]
        candidates += [host, host.split(".")[0]]
    candidates += [p for p in re.split(r"[.\-_/]", site) if len(p) > 2]
    for c in candidates:
        c = c.strip().lower()
        if c and c not in seen:
            seen.add(c)
            terms.append(c)
    return terms


def build_keywords(parts: Dict[str, str], tags: List[str],
                   rules: Dict[str, List[str]], synonyms: bool,
                   hits: Dict[str, int], syn_min: int,
                   site: str = "", base_url: str = "") -> str:
    """Inferred vocabulary. Indexed at weight 'D', the lowest.

    This is what lets "trucks" find the Volvo D13 viewer: the page never says
    "truck", but it matches the `diesel` rule, whose vocabulary includes truck,
    semi and wheeler.

    It is kept out of `content` deliberately. When synonyms lived in the prose
    column, every page that brushed a rule scored identically to the page the
    topic was actually about — "trucks" returned nine results all at rank 0.400.
    At weight D (0.1 vs prose 0.4) a real match now outranks an inherited one.
    """
    parts_out = []
    if parts["keywords"]:
        parts_out.append(parts["keywords"])
    parts_out.extend(site_terms(site, base_url))
    if tags:
        parts_out.append(", ".join(tags))
    if synonyms and tags:
        related, seen = [], set()
        # Expansion needs stronger evidence than tagging does. Injecting a
        # rule's whole vocabulary is aggressive: at the tagging threshold every
        # page that merely brushed `diesel` inherited "truck", so a truck search
        # returned nine pages tied at the same score and buried the one page
        # actually about diesel engines.
        for t in [t for t in tags if hits.get(t, 0) >= syn_min]:
            for w in rules.get(t, []):
                # Bare digits ("18") add noise and match nothing useful.
                if len(w) > 2 and w.lower() not in seen:
                    seen.add(w.lower())
                    related.append(w)
        parts_out.extend(related)
    return ", ".join(parts_out)


def collect(directory: str, rules: Dict[str, List[str]], site: str,
            base_url: str, server_name: str, synonyms: bool,
            min_hits: int, syn_min: int, clearance: int = 0) -> List[dict]:
    items = []
    for root, _, files in os.walk(directory):
        for fn in sorted(files):
            if not fn.lower().endswith(".html") or fn in SKIP_NAMES:
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, directory)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    soup = BeautifulSoup(fh.read(), "html.parser")
            except Exception as e:
                print(f"WARN unreadable {rel}: {e}", file=sys.stderr)
                continue

            parts = page_text(soup)
            title = parts["title"] or rel
            hits = tag_hits(parts, rules)
            tags = sorted([t for t, n in hits.items() if n >= min_hits],
                          key=lambda t: -hits[t])
            # A page needs real prose of its own. Without it the "content"
            # would be nothing but the tags we just inferred, which indexes a
            # near-duplicate of whatever richer page shares its title.
            if not parts["description"] and len(parts["body"]) < 40:
                print(f"SKIP {rel} — no description or body text")
                continue

            content = build_content(parts)
            keywords = build_keywords(parts, tags, rules, synonyms, hits,
                                      syn_min, site, base_url)
            if not content.strip():
                print(f"SKIP {rel} — no indexable text")
                continue

            url = ""
            if base_url:
                url = base_url.rstrip("/") + "/" + rel.replace(os.sep, "/")
                url = re.sub(r"/index\.html$", "/", url)

            # Only the page's own og:image, made absolute. There is deliberately
            # no fallback: a result with no artwork renders without artwork,
            # rather than borrowing a picture that belongs to something else.
            image = parts.get("image", "")
            if image and not image.startswith(("http://", "https://", "data:")):
                if base_url:
                    image = base_url.rstrip("/") + "/" + image.lstrip("/")
                else:
                    image = ""

            items.append({
                "serverName": server_name,
                "category": "document",
                "title": title,
                "content": content,
                "keywords": keywords,
                # Unique per page, so the (server, source, title) upsert updates
                # a page in place instead of colliding with its siblings.
                "source": f"{site}:{rel.replace(os.sep, '/')}",
                "tags": tags,
                "status": "active",
                # 0 is world-readable; 10 restricts the page to level 10
                # clearance. The API enforces it against a Keycloak role, so
                # this is a real boundary, not a display hint.
                "clearance": clearance,
                "metadata": {"url": url, "path": rel, "site": site,
                             **({"image": image} if image else {})},
            })
    return items


def main():
    ap = argparse.ArgumentParser(description="Push tagged site pages into searchsearcher")
    ap.add_argument("directory", help="Site directory to walk")
    ap.add_argument("--site", required=True, help="Short site name, e.g. diesel.tech")
    ap.add_argument("--base-url", default="", help="Public base URL, for result links")
    ap.add_argument("--api", default=os.getenv("SEARCHSEARCHER_URL", DEFAULT_API))
    ap.add_argument("--token", default=os.getenv("INGEST_TOKEN", ""))
    ap.add_argument("--server-name", default="gitlab-pages",
                    help="Which 'server' these pages are attributed to")
    ap.add_argument("--min-hits", type=int, default=2,
                    help="Distinct rule keywords a page must match to earn a tag")
    ap.add_argument("--synonym-min-hits", type=int, default=3,
                    help="Distinct keywords needed before a tag's vocabulary is injected")
    ap.add_argument("--no-synonyms", action="store_true",
                    help="Do not expand matched tags into their rule vocabulary")
    ap.add_argument("--clearance", type=int, default=0,
                    help="Access level for every page in this feed: 0 public, "
                         "10 = level 10 clearance (matomo, logger, locator, "
                         "pgadmin and other infra surfaces)")
    ap.add_argument("--dry-run", action="store_true", help="Print payloads, send nothing")
    args = ap.parse_args()

    rules = load_tag_rules()
    items = collect(args.directory, rules, args.site, args.base_url,
                    args.server_name, not args.no_synonyms, args.min_hits,
                    args.synonym_min_hits, args.clearance)
    if not items:
        print("nothing to index")
        return

    if args.dry_run:
        for it in items:
            print(f"\n--- {it['source']}")
            print(f"    title: {it['title']}")
            print(f"    tags : {', '.join(it['tags']) or '(none)'}")
            print(f"    url  : {it['metadata']['url'] or '(none)'}")
            print(f"    content ({len(it['content'])} chars): {it['content'][:140]}...")
            print(f"    keywords: {it['keywords'][:140]}")
            print(f"    clearance: {it['clearance']}")
        print(f"\nDRY RUN — {len(items)} page(s) would be pushed to {args.api}")
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
                print(f"✓ {it['source']} → {json.dumps(r.json())}")
            else:
                failed += 1
                print(f"✗ {it['source']} → {r.status_code} {r.text[:160]}", file=sys.stderr)
        except Exception as e:
            failed += 1
            print(f"✗ {it['source']} → {e}", file=sys.stderr)

    print(f"\nPushed {ok} page(s), {failed} failed → {args.api}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
