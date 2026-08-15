#!/usr/bin/env python3
"""
tagger_html_upserter.py
Walk a site directory, determine tags from page content, upsert <meta name="keywords"> safely.
Requires: beautifulsoup4
Usage:
  python tagger_html_upserter.py /path/to/site --dry-run
  python tagger_html_upserter.py /path/to/site --tags "alpha,beta"  # optional override
"""

import os
import re
import html
import sys
import tempfile
import argparse
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Dict, List

# ---------- CONFIG: tag rules ----------
TAG_RULES = {
    "news": ["breaking", "headline", "news", "report", "press release", "update"],
    "blog": ["blog", "post", "author", "read more", "subscribe", "comments"],
    "product": ["buy", "price", "pricing", "features", "download", "product", "sale"],
    "docs": ["docs", "documentation", "guide", "reference", "api", "sdk", "installation"],
    "tutorial": ["tutorial", "how to", "how-to", "step-by-step", "walkthrough", "example"],
    "faq": ["faq", "frequently asked", "questions", "answers"],
    "release": ["release", "changelog", "v", "version", "upgrade"],
    "case-study": ["case study", "customer", "testimonial", "success story"],
    "landing": ["hero", "call to action", "sign up", "get started", "try now"],
    "legal": ["privacy", "terms", "terms of service", "cookie", "gdpr", "legal"],
    "about": ["about", "mission", "team", "our story", "contact us"],
    "media": ["video", "gallery", "image", "photo", "press kit"],
    "software": ["software", "application", "code", "developer", "api"],
    "food": ["food", "restaurant", "menu", "recipe", "dining", "cuisine"],
    "services": ["service", "consulting", "cleaning", "maintenance"],
    "diesel": ["fuel", "engine", "diesel", "vehicle", "tech", "truck", "18", "wheeler", "semi"],
    "training": ["training", "course", "school", "courses", "learning"],
}

# ---------- Compile regexes once ----------
_COMPILED_TAG_RULES: Dict[str, re.Pattern] = {
    tag: re.compile(r"\b(?:" + "|".join(re.escape(k) for k in kws) + r")\b", re.IGNORECASE)
    for tag, kws in TAG_RULES.items() if kws
}

# ---------- Helpers ----------
def atomic_write(filepath: str, content: str, mode: int = 0o644, encoding: str = "utf-8"):
    if not filepath:
        raise ValueError("filepath must be set")
    parent = os.path.dirname(os.path.abspath(filepath))
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".tmp_write_", text=True)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, filepath)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def extract_body_text(soup: BeautifulSoup, *, lower: bool = True, max_len: int = 200_000) -> str:
    if not soup:
        return ""
    container = soup.body or soup.find("main") or soup.find("article") or soup
    for t in container.find_all(["script", "style", "noscript", "template", "svg"]):
        t.decompose()
    text = container.get_text(" ", strip=True) or ""
    text = re.sub(r"\s+", " ", text).strip()
    if lower:
        text = text.lower()
    if max_len and len(text) > max_len:
        text = text[:max_len].rstrip()
    return text

def normalize_and_build_keywords(matched_tags: List[str], max_len: int = 1000) -> str:
    tags = matched_tags or []
    seen = set()
    normalized = []
    for t in tags:
        if not t:
            continue
        s = t.strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(s)
    if not normalized:
        return ""
    kw = ", ".join(normalized)
    if len(kw) > max_len:
        kw = kw[:max_len].rstrip(" ,") + "…"
    return html.escape(kw)

def ensure_head_and_upsert_meta(soup: BeautifulSoup, matched_tags: List[str], *,
                                max_len: int = 1000, inject_charset: bool = True):
    # Ensure <html> root
    if not soup.html:
        html_tag = soup.new_tag("html")
        body_tag = soup.new_tag("body")
        for node in list(soup.contents):
            body_tag.append(node.extract())
        html_tag.append(body_tag)
        soup.append(html_tag)

    # Ensure <head>
    if not soup.html.head:
        head_tag = soup.new_tag("head")
        if inject_charset:
            head_tag.append(soup.new_tag("meta", charset="utf-8"))
        soup.html.insert(0, head_tag)

    head = soup.html.head
    keywords_str = normalize_and_build_keywords(matched_tags, max_len=max_len)
    existing_meta = head.find("meta", attrs={"name": "keywords"})

    if existing_meta:
        old = (existing_meta.get("content") or "").strip()
        if old and keywords_str:
            def split_vals(s): return [p.strip() for p in s.split(",") if p.strip()]
            old_list = split_vals(html.unescape(old))
            new_list = split_vals(html.unescape(keywords_str))
            seen = {t.lower() for t in old_list}
            merged = list(old_list)
            for t in new_list:
                if t.lower() not in seen:
                    merged.append(t); seen.add(t.lower())
            merged_str = ", ".join(merged)
            if len(merged_str) > max_len:
                merged_str = merged_str[:max_len].rstrip(" ,") + "…"
            existing_meta["content"] = html.escape(merged_str)
        elif keywords_str:
            existing_meta["content"] = keywords_str
        else:
            existing_meta.decompose()
    else:
        if keywords_str:
            new_meta = soup.new_tag("meta", attrs={"name": "keywords", "content": keywords_str})
            head.append(new_meta)

    return soup, keywords_str

def determine_tags_from_soup(soup: BeautifulSoup, *, fallback_untagged: bool = False) -> List[str]:
    body_text = extract_body_text(soup, lower=True)
    if not body_text:
        return ["untagged"] if fallback_untagged else []

    matched = []
    for tag, pattern in _COMPILED_TAG_RULES.items():
        try:
            if pattern.search(body_text):
                matched.append(tag)
        except Exception:
            continue

    seen = set()
    out = []
    for t in matched:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    if not out and fallback_untagged:
        return ["untagged"]
    return out

# ---------- Main walker ----------
def tag_html_files(directory: str, tags_for_file_fn=None, dry_run: bool = False, max_len: int = 1000):
    results = []
    if not directory:
        raise ValueError("directory must be provided")
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.lower().endswith(".html"):
                continue
            path = os.path.join(root, file)
            # optional: skip symlinks
            if os.path.islink(path):
                print(f"Skipping symlink {path}")
                continue
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    html_input = fh.read()
            except Exception as e:
                print(f"{datetime.utcnow().isoformat()}Z ERROR reading {path}: {e}", file=sys.stderr)
                continue

            soup = BeautifulSoup(html_input or "", "html.parser")

            if tags_for_file_fn:
                try:
                    matched_tags = tags_for_file_fn(path, soup) or []
                except Exception as e:
                    print(f"{datetime.utcnow().isoformat()}Z WARN tags_for_file_fn failed for {path}: {e}", file=sys.stderr)
                    matched_tags = []
            else:
                # default heuristic: data-tags or auto-detect via content
                body = soup.body or soup.find("article") or soup.find("main")
                matched_tags = []
                if body:
                    raw = body.get("data-tags") or body.get("data-keywords")
                    if raw:
                        matched_tags = [t.strip() for t in raw.split(",") if t.strip()]
                # if no explicit data-tags, determine from content
                if not matched_tags:
                    matched_tags = determine_tags_from_soup(soup, fallback_untagged=False)

            new_soup, keywords_str = ensure_head_and_upsert_meta(soup, matched_tags, max_len=max_len)
            out_html = str(new_soup)

            if dry_run:
                changed = (out_html != html_input)
                print(f"DRY {path} -> changed={changed} tags={keywords_str or ''}")
            else:
                if out_html != html_input:
                    try:
                        atomic_write(path, out_html)
                        print(f"Updated {path} with tags: {keywords_str or ''}")
                        changed = True
                    except Exception as e:
                        print(f"{datetime.utcnow().isoformat()}Z ERROR writing {path}: {e}", file=sys.stderr)
                        changed = False
                else:
                    print(f"No change {path} (tags: {keywords_str or ''})")
                    changed = False

            results.append({"path": path, "changed": changed, "keywords": keywords_str or ""})
    return results

# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Upsert <meta name='keywords'> from matched tags into HTML files")
    parser.add_argument("directory", help="Site directory to scan")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files; just report")
    parser.add_argument("--pretty", action="store_true", help="Write prettified HTML (debug only)")
    parser.add_argument("--tags", "-t", help="Override tags for every file (comma-separated)")
    parser.add_argument("--max-len", type=int, default=1000, help="Max length for keywords meta content")
    args = parser.parse_args()

    tags_override = None
    if args.tags:
        tags_override = [t.strip() for t in args.tags.split(",") if t.strip()]

    def tags_fn_override(path, soup):
        return tags_override

    fn = tags_fn_override if tags_override is not None else None
    results = tag_html_files(args.directory, tags_for_file_fn=fn, dry_run=args.dry_run, max_len=args.max_len)

    # summary
    updated = [r for r in results if r["changed"]]
    print(f"\nSummary: scanned {len(results)} files, updated {len(updated)} files")
    for r in updated:
        print(f" - {r['path']}: tags={r['keywords']}")

if __name__ == "__main__":
    main()
