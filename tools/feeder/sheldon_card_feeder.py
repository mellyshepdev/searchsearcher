#!/usr/bin/env python3
"""
sheldon_card_feeder.py
Extract character cards from Sheldon's battle-stages game and push to searchsearcher.

Usage:
  python3 sheldon_card_feeder.py --token "$INGEST_TOKEN"
"""

import argparse
import json
import os
import re
import sys
import requests

DEFAULT_API = "https://search.theofficialblacksheepco.com"
GAME_PATH = "/home/swoopg111/projects/sheldon-the-sheep/games/battle-stages-v2/index.html"


def extract_cards(html_path: str) -> list:
    """Parse FACTION_CARDS array from the battle-stages HTML file."""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the FACTION_CARDS array
    match = re.search(r'const FACTION_CARDS = \[(.*?)\];', content, re.DOTALL)
    if not match:
        raise SystemExit("Could not find FACTION_CARDS array in HTML file")
    
    cards_str = match.group(1)
    
    # Parse each card object
    cards = []
    # Split by }, but handle nested objects
    card_pattern = r'\{id:\'([^\']+)\'[^\}]+\}'
    for m in re.finditer(card_pattern, cards_str):
        card_id = m.group(1)
        # Extract the full card object
        start = m.start()
        # Find matching closing brace
        brace_count = 0
        i = start
        while i < len(cards_str):
            if cards_str[i] == '{':
                brace_count += 1
            elif cards_str[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    break
            i += 1
        
        card_obj_str = cards_str[start:i+1]
        cards.append({'id': card_id, 'raw': card_obj_str})
    
    return cards


def parse_card(card_str: str) -> dict:
    """Parse individual card object string into structured data."""
    card = {}
    
    # Extract fields using regex
    def extract_field(pattern):
        m = re.search(pattern, card_str)
        return m.group(1) if m else None
    
    card['id'] = extract_field(r"id:'([^']+)'")
    card['name'] = extract_field(r"name:'([^']+)'")
    card['emoji'] = extract_field(r"emoji:'([^']+)'")
    card['category'] = extract_field(r"cat:'([^']+)'")
    card['rarity'] = extract_field(r"rarity:'([^']+)'")
    card['level'] = extract_field(r"level:(\d+)")
    card['powerType'] = extract_field(r"powerType:'([^']+)'")
    card['secondType'] = extract_field(r"secondType:'([^']+)'")
    card['faction'] = extract_field(r"faction:'([^']+)'")
    card['img'] = extract_field(r"img:'([^']+)'")
    
    # Extract moves
    moves = []
    move_pattern = r'\{name:\'([^\']+)\'[^\}]+\}'
    for m in re.finditer(move_pattern, card_str):
        move_name = m.group(1)
        move_str = card_str[m.start():m.end()]
        move_icon = extract_field_from_str(move_str, r"icon:'([^']+)'")
        move_desc = extract_field_from_str(move_str, r"desc:'([^']+)'")
        moves.append({'name': move_name, 'icon': move_icon, 'desc': move_desc})
    card['moves'] = moves
    
    # Extract companions
    companions = []
    comp_pattern = r'\{name:\'([^\']+)\'[^\}]+\}'
    for m in re.finditer(comp_pattern, card_str):
        comp_name = m.group(1)
        comp_str = card_str[m.start():m.end()]
        comp_type = extract_field_from_str(comp_str, r"type:'([^']+)'")
        comp_icon = extract_field_from_str(comp_str, r"icon:'([^']+)'")
        comp_ability = extract_field_from_str(comp_str, r"ability:'([^']+)'")
        companions.append({'name': comp_name, 'type': comp_type, 'icon': comp_icon, 'ability': comp_ability})
    card['companions'] = companions
    
    return card


def extract_field_from_str(s: str, pattern: str) -> str:
    m = re.search(pattern, s)
    return m.group(1) if m else None


def build_content(card: dict) -> str:
    """Build searchable content from card data."""
    parts = []
    
    if card['name']:
        parts.append(card['name'])
    
    if card['faction']:
        parts.append(f"Faction: {card['faction']}")
    
    if card['rarity']:
        parts.append(f"Rarity: {card['rarity']}")
    
    if card['level']:
        parts.append(f"Level: {card['level']}")
    
    if card['powerType']:
        parts.append(f"Power Type: {card['powerType']}")
    
    if card['secondType']:
        parts.append(f"Secondary Type: {card['secondType']}")
    
    # Add moves
    if card['moves']:
        parts.append("Abilities:")
        for move in card['moves']:
            parts.append(f"- {move['name']}: {move['desc']}")
    
    # Add companions
    if card['companions']:
        parts.append("Companions:")
        for comp in card['companions']:
            parts.append(f"- {comp['name']} ({comp['type']}): {comp['ability']}")
    
    return "\n\n".join(parts)


def build_keywords(card: dict) -> str:
    """Build keywords for search."""
    keywords = []
    
    if card['name']:
        keywords.append(card['name'])
    
    if card['faction']:
        keywords.append(card['faction'])
    
    if card['powerType']:
        keywords.append(card['powerType'])
    
    if card['secondType']:
        keywords.append(card['secondType'])
    
    if card['rarity']:
        keywords.append(card['rarity'])
    
    # Move names
    for move in card.get('moves', []):
        keywords.append(move['name'])
    
    # Companion names
    for comp in card.get('companions', []):
        keywords.append(comp['name'])
    
    return ", ".join(keywords)


def main():
    ap = argparse.ArgumentParser(description="Ingest Sheldon battle cards into searchsearcher")
    ap.add_argument("--api", default=os.getenv("SEARCHSEARCHER_URL", DEFAULT_API))
    ap.add_argument("--token", default=os.getenv("INGEST_TOKEN", ""))
    ap.add_argument("--game-path", default=GAME_PATH)
    ap.add_argument("--server-name", default="sheldon-universe")
    ap.add_argument("--dry-run", action="store_true", help="Print payloads, send nothing")
    args = ap.parse_args()
    
    if not os.path.exists(args.game_path):
        raise SystemExit(f"Game file not found: {args.game_path}")
    
    print(f"Parsing cards from {args.game_path}...")
    cards = extract_cards(args.game_path)
    print(f"Found {len(cards)} card definitions")
    
    items = []
    for card_data in cards:
        card = parse_card(card_data['raw'])
        
        content = build_content(card)
        keywords = build_keywords(card)
        
        # Build image URL
        img = card.get('img', '')
        if img and not img.startswith('http'):
            img = f"https://sheldonthesheep.theofficialblacksheepco.store/games/battle-stages-v2/{img}"
        
        item = {
            "serverName": args.server_name,
            "category": "document",
            "title": card.get('name', card.get('id', 'Unknown')),
            "content": content,
            "keywords": keywords,
            "source": f"sheldon-cards:{card['id']}",
            "tags": [card.get('category', 'character'), card.get('faction', 'no-faction')] if card.get('faction') else [card.get('category', 'character')],
            "status": "active",
            "clearance": 0,
            "metadata": {
                "cardId": card['id'],
                "emoji": card.get('emoji', ''),
                "rarity": card.get('rarity', ''),
                "level": card.get('level', ''),
                "powerType": card.get('powerType', ''),
                "secondType": card.get('secondType', ''),
                "faction": card.get('faction', ''),
                "image": img,
                "url": f"https://sheldonthesheep.theofficialblacksheepco.store/games/battle-stages-v2/"
            }
        }
        items.append(item)
    
    if args.dry_run:
        for it in items:
            print(f"\n--- {it['source']}")
            print(f"    title: {it['title']}")
            print(f"    tags : {', '.join(it['tags'])}")
            print(f"    image: {it['metadata'].get('image') or '(none)'}")
            print(f"    content ({len(it['content'])} chars): {it['content'][:200]}...")
        print(f"\nDRY RUN — {len(items)} card(s) would be pushed to {args.api}")
        return
    
    if not args.token:
        raise SystemExit("no ingest token: pass --token or set INGEST_TOKEN")
    
    ok = failed = 0
    for it in items:
        try:
            r = requests.post(
                f"{args.api}/api/ingest",
                json=it,
                timeout=30,
                headers={
                    "Authorization": f"Bearer {args.token}",
                    "X-Ingest-Token": args.token
                }
            )
            if r.status_code == 200:
                ok += 1
                print(f"✓ {it['source']} → {json.dumps(r.json())}")
            else:
                failed += 1
                print(f"✗ {it['source']} → {r.status_code} {r.text[:160]}", file=sys.stderr)
        except Exception as e:
            failed += 1
            print(f"✗ {it['source']} → {e}", file=sys.stderr)
    
    print(f"\nPushed {ok} card(s), {failed} failed → {args.api}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
