import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { searchableItems, servers } from "@/db/schema";
import { sql, eq, and, or, ilike, lte, SQL } from "drizzle-orm";
import type { ItemCategory, ItemStatus } from "@/types/search";
import { clearanceFor, PUBLIC_CLEARANCE } from "@/lib/clearance";

const VALID_CATEGORIES: ItemCategory[] = [
  "log",
  "container",
  "app",
  "program",
  "document",
  "config",
  "metric",
  "alert",
  "service",
  "database",
];

const VALID_STATUSES: ItemStatus[] = [
  "active",
  "inactive",
  "error",
  "warning",
  "stopped",
  "pending",
  "completed",
  "failed",
];

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get("q")?.trim() || "";
  const category = searchParams.get("category")?.trim() || "";
  const serverId = searchParams.get("serverId")?.trim() || "";
  const status = searchParams.get("status")?.trim() || "";
  const limit = Math.min(parseInt(searchParams.get("limit") || "50"), 200);
  const offset = parseInt(searchParams.get("offset") || "0");

  if (!query && !category && !serverId && !status) {
    return NextResponse.json(
      { error: "At least one filter (q, category, serverId, status) is required" },
      { status: 400 }
    );
  }

  // What this caller may read is decided from their bearer token, never from a
  // parameter. Unauthenticated and unprivileged callers get public rows only —
  // the browser is not trusted to filter, because it never could.
  const { level, reason } = await clearanceFor(
    request.headers.get("authorization")
  );

  try {
    const results = await executeSearch(
      query,
      category,
      serverId,
      status,
      limit,
      offset,
      level
    );

    return NextResponse.json({
      clearance: level,
      clearanceReason: level > PUBLIC_CLEARANCE ? undefined : reason,
      results: results.items.map((r) => ({
        ...r,
        metadata: r.metadata ? JSON.parse(r.metadata) : null,
      })),
      total: results.total,
      limit,
      offset,
      query,
    });
  } catch (error) {
    console.error("Search error, falling back to ILIKE:", error);
    try {
      const results = await executeFallbackSearch(
        query,
        category,
        serverId,
        status,
        limit,
        offset,
        level
      );
      return NextResponse.json({
        clearance: level,
        results: results.items.map((r) => ({
          ...r,
          metadata: r.metadata ? JSON.parse(r.metadata) : null,
        })),
        total: results.total,
        limit,
        offset,
        query,
      });
    } catch (fallbackError) {
      console.error("Fallback search error:", fallbackError);
      return NextResponse.json({ error: "Search failed" }, { status: 500 });
    }
  }
}

// Must match schema.ts's search_gin_idx expression character-for-character (same function
// calls/operands) or Postgres silently stops using the index and falls back to a seq scan.
function weightedVector() {
  return sql`(
    setweight(to_tsvector('english', ${searchableItems.title}), 'A') ||
    setweight(to_tsvector('english', coalesce(${searchableItems.content}, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(${searchableItems.keywords}, '')), 'D')
  )`;
}

async function executeSearch(
  query: string,
  category: string,
  serverId: string,
  status: string,
  limit: number,
  offset: number,
  maxClearance: number
) {
  const conditions: SQL[] = [lte(searchableItems.clearance, maxClearance)];
  let rankExpr: SQL<number> | null = null;

  if (query) {
    // Type-ahead prefix match — this UI is live-search-as-you-type (SearchBar.tsx fires on
    // every keystroke, no submit/Enter surface exists yet), so websearch_to_tsquery's phrase
    // parsing doesn't apply here; if a submit-on-Enter surface is added later, that's the mode
    // to use websearch_to_tsquery for instead.
    // Split on any run of non-alphanumeric characters, not just whitespace:
    // a bare word like "tech-estate" produced the single token "tech-estate:*",
    // which to_tsquery rejects outright (Postgres error 42601, tsquery.c
    // makepol) - every hyphenated/punctuated query silently fell through to
    // the ILIKE fallback below instead of actually ranking. Splitting into
    // separate ANDed prefix terms ("tech:* & estate:*") also matches more
    // real content, since compound service names are not always hyphenated
    // the same way in the text being searched.
    const tsQuery = query
      .split(/[^a-zA-Z0-9]+/)
      .filter(Boolean)
      .map((w) => `${w}:*`)
      .join(" & ");

    const vector = weightedVector();
    conditions.push(sql`${vector} @@ to_tsquery('english', ${tsQuery})`);
    rankExpr = sql<number>`ts_rank_cd(${vector}, to_tsquery('english', ${tsQuery}))`;
  }

  if (category && VALID_CATEGORIES.includes(category as ItemCategory)) {
    conditions.push(
      eq(
        searchableItems.category,
        category as (typeof VALID_CATEGORIES)[number]
      )
    );
  }

  if (serverId) {
    conditions.push(eq(searchableItems.serverId, parseInt(serverId)));
  }

  if (status && VALID_STATUSES.includes(status as ItemStatus)) {
    conditions.push(
      eq(searchableItems.status, status as (typeof VALID_STATUSES)[number])
    );
  }

  const whereClause =
    conditions.length > 0 ? and(...conditions) : sql`true`;

  const items = await db
    .select({
      id: searchableItems.id,
      category: searchableItems.category,
      title: searchableItems.title,
      content: searchableItems.content,
      metadata: searchableItems.metadata,
      status: searchableItems.status,
      severity: searchableItems.severity,
      source: searchableItems.source,
      tags: searchableItems.tags,
      clearance: searchableItems.clearance,
      createdAt: searchableItems.createdAt,
      serverId: searchableItems.serverId,
      serverName: servers.name,
      serverHostname: servers.hostname,
      serverLocation: servers.location,
      ...(rankExpr ? { rank: rankExpr } : {}),
    })
    .from(searchableItems)
    .innerJoin(servers, eq(searchableItems.serverId, servers.id))
    .where(whereClause)
    .orderBy(
      rankExpr ? sql`${rankExpr} DESC` : sql`${searchableItems.createdAt} DESC`
    )
    .limit(limit)
    .offset(offset);

  const countResult = await db
    .select({ count: sql<number>`count(*)::int` })
    .from(searchableItems)
    .innerJoin(servers, eq(searchableItems.serverId, servers.id))
    .where(whereClause);

  return { items, total: countResult[0]?.count ?? 0 };
}

async function executeFallbackSearch(
  query: string,
  category: string,
  serverId: string,
  status: string,
  limit: number,
  offset: number,
  maxClearance: number
) {
  const conditions: SQL[] = [lte(searchableItems.clearance, maxClearance)];

  if (query) {
    conditions.push(
      or(
        ilike(searchableItems.title, `%${query}%`),
        ilike(searchableItems.content, `%${query}%`),
        ilike(searchableItems.keywords, `%${query}%`)
      )!
    );
  }

  if (category && VALID_CATEGORIES.includes(category as ItemCategory)) {
    conditions.push(
      eq(
        searchableItems.category,
        category as (typeof VALID_CATEGORIES)[number]
      )
    );
  }

  if (serverId) {
    conditions.push(eq(searchableItems.serverId, parseInt(serverId)));
  }

  if (status && VALID_STATUSES.includes(status as ItemStatus)) {
    conditions.push(
      eq(searchableItems.status, status as (typeof VALID_STATUSES)[number])
    );
  }

  const whereClause =
    conditions.length > 0 ? and(...conditions) : sql`true`;

  const items = await db
    .select({
      id: searchableItems.id,
      category: searchableItems.category,
      title: searchableItems.title,
      content: searchableItems.content,
      metadata: searchableItems.metadata,
      status: searchableItems.status,
      severity: searchableItems.severity,
      source: searchableItems.source,
      tags: searchableItems.tags,
      clearance: searchableItems.clearance,
      createdAt: searchableItems.createdAt,
      serverId: searchableItems.serverId,
      serverName: servers.name,
      serverHostname: servers.hostname,
      serverLocation: servers.location,
    })
    .from(searchableItems)
    .innerJoin(servers, eq(searchableItems.serverId, servers.id))
    .where(whereClause)
    .orderBy(sql`${searchableItems.createdAt} DESC`)
    .limit(limit)
    .offset(offset);

  const countResult = await db
    .select({ count: sql<number>`count(*)::int` })
    .from(searchableItems)
    .innerJoin(servers, eq(searchableItems.serverId, servers.id))
    .where(whereClause);

  return { items, total: countResult[0]?.count ?? 0 };
}
