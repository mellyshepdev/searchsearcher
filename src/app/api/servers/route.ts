import { NextResponse } from "next/server";
import { db } from "@/db";
import { servers, searchableItems } from "@/db/schema";
import { sql, eq } from "drizzle-orm";

export async function GET() {
  try {
    const allServers = await db
      .select({
        id: servers.id,
        name: servers.name,
        hostname: servers.hostname,
        ipAddress: servers.ipAddress,
        location: servers.location,
        status: servers.status,
        os: servers.os,
        tags: servers.tags,
        itemCount: sql<number>`count(${searchableItems.id})::int`,
      })
      .from(servers)
      .leftJoin(searchableItems, eq(servers.id, searchableItems.serverId))
      .groupBy(servers.id)
      .orderBy(servers.name);

    return NextResponse.json({ servers: allServers });
  } catch (error) {
    console.error("Servers fetch error:", error);
    return NextResponse.json(
      { error: "Failed to fetch servers" },
      { status: 500 }
    );
  }
}
