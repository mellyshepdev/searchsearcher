import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";

// The pool is created lazily on first use, NOT at import time: Next.js
// imports these modules while building (page-data collection), where no
// DATABASE_URL exists. Connecting on first request keeps builds green.

const globalForDb = globalThis as typeof globalThis & {
  __arenaNextJsPostgresqlPool?: Pool;
};

let _pool: Pool | undefined;
let _db: ReturnType<typeof drizzle> | undefined;

function getPool(): Pool {
  if (globalForDb.__arenaNextJsPostgresqlPool) return globalForDb.__arenaNextJsPostgresqlPool;
  if (!_pool) {
    const databaseUrl = process.env.DATABASE_URL;
    if (!databaseUrl) {
      throw new Error("DATABASE_URL is required");
    }
    _pool = new Pool({ connectionString: databaseUrl });
    if (process.env.NODE_ENV !== "production") {
      globalForDb.__arenaNextJsPostgresqlPool = _pool;
    }
  }
  return _pool;
}

function getDb() {
  if (!_db) _db = drizzle(getPool());
  return _db;
}

function lazy<T extends object>(resolve: () => T): T {
  return new Proxy({} as T, {
    get(_target, prop) {
      const instance = resolve() as Record<PropertyKey, unknown>;
      const value = instance[prop];
      return typeof value === "function" ? (value as (...a: unknown[]) => unknown).bind(instance) : value;
    },
  });
}

export const pool: Pool = lazy(getPool);
export const db: ReturnType<typeof drizzle> = lazy(getDb);
