"use client";

import { useState } from "react";
import {
  CATEGORY_CONFIG,
  STATUS_CONFIG,
} from "@/types/search";
import type { SearchResult, ItemCategory, ItemStatus } from "@/types/search";

interface ResultsListProps {
  results: SearchResult[];
  loading: boolean;
  searched: boolean;
  query: string;
  total: number;
}

function highlightText(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;
  const words = query
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (words.length === 0) return text;

  const regex = new RegExp(`(${words.join("|")})`, "gi");
  const parts = text.split(regex);

  return parts.map((part, i) =>
    words.some((w) => part.toLowerCase() === w.toLowerCase()) ? (
      <mark key={i}>{part}</mark>
    ) : (
      part
    )
  );
}

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return date.toLocaleDateString();
}

function ResultCard({
  result,
  query,
}: {
  result: SearchResult;
  query: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const catConfig =
    CATEGORY_CONFIG[result.category as ItemCategory];
  const statConfig = result.status
    ? STATUS_CONFIG[result.status as ItemStatus]
    : null;

  return (
    <div
      className="animate-fade-in group bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-xl hover:border-white/20 hover:bg-white/[0.06] transition-all duration-150"
    >
      <div className="p-4">
        {/* Top row: category badge, status, server, time */}
        <div className="flex flex-wrap items-center gap-2 mb-2">
          {catConfig && (
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded-md border ${catConfig.bgColor} ${catConfig.color}`}
            >
              <span>{catConfig.icon}</span>
              {catConfig.label}
            </span>
          )}
          {statConfig && (
            <span
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] font-medium rounded-md ${statConfig.color}`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${statConfig.dotColor}`}
              />
              {statConfig.label}
            </span>
          )}
          {result.severity && (
            <span
              className={`inline-flex items-center px-2 py-0.5 text-[11px] font-semibold rounded-md ${
                result.severity === "critical"
                  ? "bg-red-400/15 text-red-300"
                  : result.severity === "high"
                  ? "bg-orange-400/15 text-orange-300"
                  : result.severity === "medium"
                  ? "bg-amber-400/15 text-amber-300"
                  : result.severity === "info"
                  ? "bg-sky-400/15 text-sky-300"
                  : "bg-white/10 text-white/60"
              }`}
            >
              {result.severity}
            </span>
          )}
          <div className="flex-1" />
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] text-white/50 bg-white/[0.04] rounded-md border border-white/10"
            title={`${result.serverHostname} - ${result.serverLocation}`}
          >
            <svg
              className="w-3 h-3 text-white/35"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"
              />
            </svg>
            {result.serverName}
          </span>
          <span className="text-[11px] text-white/35">
            {timeAgo(result.createdAt)}
          </span>
        </div>

        {/* Title */}
        <h3 className="text-sm font-semibold text-white group-hover:text-sky-300 transition-colors">
          {highlightText(result.title, query)}
        </h3>

        {/* Content preview */}
        {result.content && (
          <p
            className={`mt-1 text-sm text-white/60 ${
              expanded ? "" : "line-clamp-2"
            }`}
          >
            {highlightText(result.content, query)}
          </p>
        )}

        {/* Tags and source */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {result.source && (
            <span className="inline-flex items-center gap-1 text-[10px] text-white/35 font-mono">
              <svg
                className="w-3 h-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
                />
              </svg>
              {result.source}
            </span>
          )}
          {result.tags &&
            result.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center px-2 py-0.5 text-[10px] text-white/50 bg-white/[0.04] rounded-full border border-white/10"
              >
                {tag}
              </span>
            ))}
          {/* Expand/collapse */}
          {(result.content && result.content.length > 150) ||
          result.metadata ? (
            <button
              onClick={() => setExpanded(!expanded)}
              className="ml-auto text-[11px] text-sky-400 hover:text-sky-300 font-medium"
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          ) : null}
        </div>

        {/* Expanded metadata */}
        {expanded && result.metadata && (
          <div className="mt-3 p-3 bg-black/20 rounded-lg border border-white/10">
            <p className="text-[10px] font-semibold text-white/40 uppercase tracking-wider mb-2">
              Metadata
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(result.metadata).map(([key, value]) => (
                <div key={key}>
                  <span className="text-[10px] text-white/35 block">
                    {key}
                  </span>
                  <span className="text-xs text-white/80 font-medium">
                    {typeof value === "object"
                      ? JSON.stringify(value)
                      : String(value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ResultsList({
  results,
  loading,
  searched,
  query,
  total,
}: ResultsListProps) {
  // Loading skeleton
  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="bg-white/[0.04] border border-white/10 rounded-xl p-4"
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="skeleton w-16 h-5 rounded-md" />
              <div className="skeleton w-14 h-5 rounded-md" />
              <div className="flex-1" />
              <div className="skeleton w-20 h-5 rounded-md" />
            </div>
            <div className="skeleton w-3/4 h-5 rounded mb-2" />
            <div className="skeleton w-full h-4 rounded mb-1" />
            <div className="skeleton w-2/3 h-4 rounded" />
            <div className="flex gap-2 mt-3">
              <div className="skeleton w-24 h-4 rounded" />
              <div className="skeleton w-16 h-4 rounded-full" />
              <div className="skeleton w-16 h-4 rounded-full" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Empty state - not searched yet
  if (!searched) {
    return (
      <div className="text-center py-16">
        <div className="w-20 h-20 rounded-2xl bg-sky-400/10 border border-sky-400/20 flex items-center justify-center mx-auto mb-4">
          <svg
            className="w-10 h-10 text-sky-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-white/80">
          Search across all your servers
        </h3>
        <p className="mt-1 text-sm text-white/50 max-w-md mx-auto">
          Type a query or select a category to search through logs, containers,
          applications, programs, documents, and more across all connected servers.
        </p>
        <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 gap-3 max-w-lg mx-auto">
          {[
            { icon: "📋", label: "Logs", count: "Application & system logs" },
            {
              icon: "🐳",
              label: "Containers",
              count: "Docker containers",
            },
            {
              icon: "🚀",
              label: "Applications",
              count: "Running applications",
            },
            {
              icon: "📄",
              label: "Documents",
              count: "Runbooks & guides",
            },
            {
              icon: "🔔",
              label: "Alerts",
              count: "Active & resolved",
            },
            {
              icon: "🗄️",
              label: "Databases",
              count: "Database instances",
            },
          ].map((item) => (
            <div
              key={item.label}
              className="p-3 bg-white/[0.04] rounded-lg border border-white/10 text-center"
            >
              <span className="text-2xl block mb-1">{item.icon}</span>
              <span className="text-xs font-semibold text-white/80 block">
                {item.label}
              </span>
              <span className="text-[10px] text-white/35">{item.count}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // No results
  if (results.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="w-16 h-16 rounded-2xl bg-white/[0.04] border border-white/10 flex items-center justify-center mx-auto mb-4">
          <span className="text-3xl">🔍</span>
        </div>
        <h3 className="text-lg font-semibold text-white/80">
          No results found
        </h3>
        <p className="mt-1 text-sm text-white/50">
          No items match &ldquo;{query}&rdquo;. Try different keywords or adjust
          your filters.
        </p>
      </div>
    );
  }

  // Results grouped by category
  const grouped = new Map<string, SearchResult[]>();
  for (const result of results) {
    const key = result.category;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(result);
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        {results.map((result) => (
          <ResultCard key={result.id} result={result} query={query} />
        ))}
      </div>

      {total > results.length && (
        <div className="text-center py-4 text-sm text-white/50">
          Showing {results.length} of {total} results. Refine your search for
          more specific results.
        </div>
      )}
    </div>
  );
}
