import { NextResponse } from "next/server";
import { db } from "@/db";
import { servers, searchableItems } from "@/db/schema";
import { sql, eq } from "drizzle-orm";

export async function GET() {
  try {
    // Category counts
    const categoryCounts = await db
      .select({
        category: searchableItems.category,
        count: sql<number>`count(*)::int`,
      })
      .from(searchableItems)
      .groupBy(searchableItems.category);

    // Status counts
    const statusCounts = await db
      .select({
        status: searchableItems.status,
        count: sql<number>`count(*)::int`,
      })
      .from(searchableItems)
      .groupBy(searchableItems.status);

    // Server counts
    const serverCounts = await db
      .select({
        serverId: servers.id,
        serverName: servers.name,
        serverStatus: servers.status,
        count: sql<number>`count(${searchableItems.id})::int`,
      })
      .from(servers)
      .leftJoin(searchableItems, eq(servers.id, searchableItems.serverId))
      .groupBy(servers.id, servers.name, servers.status)
      .orderBy(servers.name);

    // Total items
    const totalResult = await db
      .select({ count: sql<number>`count(*)::int` })
      .from(searchableItems);

    // Severity breakdown for alerts/logs
    const severityCounts = await db
      .select({
        severity: searchableItems.severity,
        count: sql<number>`count(*)::int`,
      })
      .from(searchableItems)
      .where(sql`${searchableItems.severity} IS NOT NULL`)
      .groupBy(searchableItems.severity);

    return NextResponse.json({
      totalItems: totalResult[0]?.count ?? 0,
      categoryCounts: Object.fromEntries(
        categoryCounts.map((c) => [c.category, c.count])
      ),
      statusCounts: Object.fromEntries(
        statusCounts.map((s) => [s.status, s.count])
      ),
      serverCounts: serverCounts.map((s) => ({
        id: s.serverId,
        name: s.serverName,
        status: s.serverStatus,
        count: s.count,
      })),
      severityCounts: Object.fromEntries(
        severityCounts.map((s) => [s.severity, s.count])
      ),
    });
  } catch (error) {
    console.error("Stats error:", error);
    return NextResponse.json(
      { error: "Failed to fetch stats" },
      { status: 500 }
    );
  }
}
