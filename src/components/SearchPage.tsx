"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import SearchBar from "./SearchBar";
import FilterBar from "./FilterBar";
import ResultsList from "./ResultsList";
import StatsPanel from "./StatsPanel";
import type { SearchResult, StatsData, ServerInfo } from "@/types/search";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [serverId, setServerId] = useState("");
  const [status, setStatus] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [searched, setSearched] = useState(false);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [servers, setServers] = useState<ServerInfo[]>([]);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const reqSeq = useRef(0);
  const PAGE_SIZE = 25;

  // Fetch servers and stats on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/servers");
        const data = await res.json();
        if (!cancelled && data.servers) setServers(data.servers);
      } catch (err) {
        console.error("Failed to fetch servers:", err);
      }
    })();
    (async () => {
      try {
        const res = await fetch("/api/stats");
        const data = await res.json();
        if (!cancelled) setStats(data);
      } catch (err) {
        console.error("Failed to fetch stats:", err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const performSearch = useCallback(
    async (
      q: string,
      cat: string,
      srv: string,
      st: string,
      offset = 0,
      append = false
    ) => {
      if (!q.trim() && !cat && !srv) {
        reqSeq.current++;
        setResults([]);
        setTotal(0);
        setHasMore(false);
        setSearched(false);
        setLoading(false);
        setLoadingMore(false);
        nextOffsetRef.current = 0;
        return;
      }

      const seq = ++reqSeq.current;
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setSearched(true);

      try {
        const params = new URLSearchParams();
        if (q.trim()) params.set("q", q.trim());
        if (cat) params.set("category", cat);
        if (srv) params.set("serverId", srv);
        if (st) params.set("status", st);
        params.set("limit", String(PAGE_SIZE));
        params.set("offset", String(offset));

        const res = await fetch(`/api/search?${params.toString()}`);
        const data = await res.json();

        // A newer request superseded this one while it was in flight.
        if (seq !== reqSeq.current) return;

        if (data.results) {
          const incoming: SearchResult[] = data.results;
          setResults((prev) => {
            const merged = append ? [...prev, ...incoming] : incoming;
            const seen = new Set<number>();
            return merged.filter((r) =>
              seen.has(r.id) ? false : (seen.add(r.id), true)
            );
          });
          setTotal(data.total);
          // Progress by rows fetched, not rows kept, so a deduped page can
          // never wedge the pager on an overlapping offset.
          const nextOffset = offset + incoming.length;
          nextOffsetRef.current = nextOffset;
          setHasMore(incoming.length > 0 && nextOffset < data.total);
        } else if (!append) {
          setResults([]);
          setTotal(0);
          setHasMore(false);
          nextOffsetRef.current = 0;
        } else {
          setHasMore(false);
        }
      } catch (err) {
        console.error("Search error:", err);
        if (!append) {
          setResults([]);
          setTotal(0);
          setHasMore(false);
        }
      } finally {
        if (seq === reqSeq.current) {
          setLoading(false);
          setLoadingMore(false);
        }
      }
    },
    [PAGE_SIZE]
  );

  const nextOffsetRef = useRef(0);
  const loadMore = useCallback(() => {
    if (loading || loadingMore || !hasMore) return;
    performSearch(query, category, serverId, status, nextOffsetRef.current, true);
  }, [
    loading,
    loadingMore,
    hasMore,
    performSearch,
    query,
    category,
    serverId,
    status,
  ]);

  // Debounced search on query/filter changes
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(() => {
      performSearch(query, category, serverId, status);
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, category, serverId, status, performSearch]);

  const isEmpty = servers.length === 0 && !stats?.totalItems;

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-black/40 backdrop-blur-xl border-b border-white/10">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-400 to-sky-600 flex items-center justify-center shadow-[0_0_16px_rgba(56,189,248,0.35)]">
                <svg
                  className="w-4 h-4 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
              </div>
              <div>
                <h1 className="text-sm font-semibold text-white tracking-tight">
                  Server Search
                </h1>
                <p className="text-[10px] text-white/50 -mt-0.5">
                  Cross-server unified search
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {servers.length > 0 && (
                <div className="hidden sm:flex items-center gap-1.5 text-xs text-white/50">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse-dot" />
                  {servers.filter((s) => s.status === "online").length} of{" "}
                  {servers.length} servers online
                </div>
              )}
              {isEmpty && (
                <span className="text-xs text-white/40">
                  Waiting for the first agent push&hellip;
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Search Section */}
        <div className="mb-6">
          <div className="text-center mb-4">
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Search everything across{" "}
              <span className="text-sky-400">all servers</span>
            </h2>
            <p className="mt-1 text-sm text-white/50">
              Logs, containers, apps, programs, documents, configs, metrics,
              alerts, services &amp; databases
            </p>
          </div>
          <SearchBar query={query} onChange={setQuery} />
        </div>

        {/* Filters */}
        <FilterBar
          category={category}
          serverId={serverId}
          status={status}
          servers={servers}
          onCategoryChange={setCategory}
          onServerChange={setServerId}
          onStatusChange={setStatus}
          total={total}
          searched={searched}
        />

        {/* Content */}
        <div className="mt-6 flex gap-6">
          {/* Results */}
          <div className="flex-1 min-w-0">
            <ResultsList
              results={results}
              loading={loading}
              loadingMore={loadingMore}
              searched={searched}
              query={query}
              total={total}
              hasMore={hasMore}
              onLoadMore={loadMore}
            />
          </div>

          {/* Stats Sidebar */}
          {stats && (
            <aside className="hidden lg:block w-72 flex-shrink-0">
              <StatsPanel stats={stats} servers={servers} />
            </aside>
          )}
        </div>
      </main>
    </div>
  );
}
