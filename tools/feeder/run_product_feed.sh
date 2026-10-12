#!/usr/bin/env bash
# Hourly product re-index on unit4 (crontab). Reads the ingest token from the
# running app container at run time, so it is never stored in a file or the
# crontab.
set -euo pipefail
TOOLS=/home/swoopg111/projects/searchsearcher/tools
tok=$(docker inspect searchsearcher-app --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^INGEST_TOKEN=//p')
[ -n "$tok" ] || { echo "$(date -u +%FT%TZ) no INGEST_TOKEN on searchsearcher-app"; exit 1; }
printf '%s %s\n' "$(date -u +%FT%TZ)" "$(docker run --rm -e INGEST_TOKEN="$tok" -v "$TOOLS":/t:ro python:3.12-alpine sh -c \
  'pip -q install --root-user-action=ignore requests >/dev/null 2>&1; python /t/feeder/product_feeder.py --api http://100.123.158.58:8219' 2>&1 | tail -3)"
