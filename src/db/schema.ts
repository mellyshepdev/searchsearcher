import {
  pgTable,
  varchar,
  text,
  timestamp,
  integer,
  index,
  unique,
  pgEnum,
} from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";

// ── Enums ──────────────────────────────────────────────────────────────────────

export const serverStatusEnum = pgEnum("server_status", [
  "online",
  "offline",
  "maintenance",
  "degraded",
]);

export const itemCategoryEnum = pgEnum("item_category", [
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
]);

export const itemStatusEnum = pgEnum("item_status", [
  "active",
  "inactive",
  "error",
  "warning",
  "stopped",
  "pending",
  "completed",
  "failed",
]);

// ── Servers ────────────────────────────────────────────────────────────────────

export const servers = pgTable(
  "servers",
  {
    id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
    name: varchar("name", { length: 100 }).notNull(),
    hostname: varchar("hostname", { length: 255 }).notNull(),
    ipAddress: varchar("ip_address", { length: 45 }).notNull(),
    location: varchar("location", { length: 255 }).notNull(),
    status: serverStatusEnum("status").notNull().default("online"),
    os: varchar("os", { length: 100 }),
    tags: text("tags").array(),
    createdAt: timestamp("created_at").notNull().defaultNow(),
    updatedAt: timestamp("updated_at").notNull().defaultNow(),
  },
  (table) => [unique("servers_name_unique").on(table.name)]
);

// ── Searchable Items (unified index) ───────────────────────────────────────────

export const searchableItems = pgTable(
  "searchable_items",
  {
    id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
    serverId: integer("server_id")
      .notNull()
      .references(() => servers.id, { onDelete: "cascade" }),
    category: itemCategoryEnum("category").notNull(),
    title: varchar("title", { length: 500 }).notNull(),
    content: text("content"),
    metadata: text("metadata"), // JSON string for extra fields
    status: itemStatusEnum("status").default("active"),
    severity: varchar("severity", { length: 20 }),
    source: varchar("source", { length: 255 }),
    tags: text("tags").array(),
    createdAt: timestamp("created_at").notNull().defaultNow(),
    updatedAt: timestamp("updated_at").notNull().defaultNow(),
  },
  (table) => [
    index("category_idx").on(table.category),
    index("server_idx").on(table.serverId),
    index("status_idx").on(table.status),
    index("tags_idx").using("gin", table.tags),
    // Full-text search index — title weighted 'A' (highest), content weighted 'B'.
    // Must match the search route's to_tsvector(...) expression character-for-character
    // or Postgres silently falls back to a sequential scan.
    index("search_gin_idx").using(
      "gin",
      sql`(
        setweight(to_tsvector('english', ${table.title}), 'A') ||
        setweight(to_tsvector('english', coalesce(${table.content}, '')), 'B')
      )`
    ),
  ]
);
