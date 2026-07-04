import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { searchableItems, servers } from "@/db/schema";
import { eq, and } from "drizzle-orm";
import type { ItemCategory, ItemStatus } from "@/types/search";

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

interface IngestBody {
  serverName: string;
  category: ItemCategory;
  title: string;
  content?: string;
  source?: string;
  tags?: string[];
  status?: ItemStatus;
  severity?: string;
  metadata?: Record<string, unknown>;
}

export async function POST(request: NextRequest) {
  const auth = request.headers.get("authorization");
  if (auth !== `Bearer ${process.env.INGEST_TOKEN}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  let body: IngestBody;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  if (!body.serverName || !body.category || !body.title) {
    return NextResponse.json(
      { error: "serverName, category, and title are required" },
      { status: 400 }
    );
  }
  if (!VALID_CATEGORIES.includes(body.category)) {
    return NextResponse.json({ error: "invalid category" }, { status: 400 });
  }
  if (body.status && !VALID_STATUSES.includes(body.status)) {
    return NextResponse.json({ error: "invalid status" }, { status: 400 });
  }

  const source = body.source ?? "unknown";

  // Agents identify by hostname/name, not numeric id — upsert the server row first.
  const [server] = await db
    .insert(servers)
    .values({
      name: body.serverName,
      hostname: body.serverName,
      ipAddress: "0.0.0.0",
      location: "unit",
    })
    .onConflictDoUpdate({
      target: servers.name,
      set: { updatedAt: new Date() },
    })
    .returning();

  // Upsert item keyed on (serverId, source, title) so re-pushes update in place instead of
  // duplicating rows — this is what makes the ingest endpoint safe to call on every run.
  const [existing] = await db
    .select({ id: searchableItems.id })
    .from(searchableItems)
    .where(
      and(
        eq(searchableItems.serverId, server.id),
        eq(searchableItems.source, source),
        eq(searchableItems.title, body.title)
      )
    )
    .limit(1);

  const metadata = body.metadata ? JSON.stringify(body.metadata) : null;

  if (existing) {
    await db
      .update(searchableItems)
      .set({
        content: body.content ?? null,
        status: body.status ?? "active",
        severity: body.severity ?? null,
        tags: body.tags ?? null,
        metadata,
        updatedAt: new Date(),
      })
      .where(eq(searchableItems.id, existing.id));
    return NextResponse.json({ id: existing.id, updated: true });
  }

  const [row] = await db
    .insert(searchableItems)
    .values({
      serverId: server.id,
      category: body.category,
      title: body.title,
      content: body.content ?? null,
      source,
      tags: body.tags ?? null,
      status: body.status ?? "active",
      severity: body.severity ?? null,
      metadata,
    })
    .returning();

  return NextResponse.json({ id: row.id, updated: false });
}
