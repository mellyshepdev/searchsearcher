"use client";

import {
  CATEGORY_CONFIG,
  STATUS_CONFIG,
  SERVER_STATUS_CONFIG,
} from "@/types/search";
import type { ServerInfo, ItemCategory, ItemStatus } from "@/types/search";

interface FilterBarProps {
  category: string;
  serverId: string;
  status: string;
  servers: ServerInfo[];
  onCategoryChange: (value: string) => void;
  onServerChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  total: number;
  searched: boolean;
}

const CATEGORIES = Object.entries(CATEGORY_CONFIG);

export default function FilterBar({
  category,
  serverId,
  status,
  servers,
  onCategoryChange,
  onServerChange,
  onStatusChange,
  total,
  searched,
}: FilterBarProps) {
  const hasFilters = category || serverId || status;

  return (
    <div className="space-y-3">
      {/* Category pills */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-white/50 mr-1">
          Category:
        </span>
        <button
          onClick={() => onCategoryChange("")}
          className={`inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-lg border transition-all duration-150 ${
            !category
              ? "bg-sky-400/15 text-sky-300 border-sky-400/30"
              : "bg-white/[0.04] text-white/60 border-white/10 hover:border-white/25"
          }`}
        >
          All
        </button>
        {CATEGORIES.map(([key, config]) => (
          <button
            key={key}
            onClick={() => onCategoryChange(category === key ? "" : key)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-all duration-150 ${
              category === key
                ? `${config.bgColor} ${config.color}`
                : "bg-white/[0.04] text-white/60 border-white/10 hover:border-white/25"
            }`}
          >
            <span className="text-sm">{config.icon}</span>
            {config.label}
          </button>
        ))}
      </div>

      {/* Server and Status filters */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Server filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-white/50">Server:</span>
          <select
            value={serverId}
            onChange={(e) => onServerChange(e.target.value)}
            className="text-xs bg-white/[0.04] border border-white/10 rounded-lg px-3 py-1.5 text-white/80 focus:outline-none focus:border-sky-400/50 focus:ring-1 focus:ring-sky-400/25"
          >
            <option value="">All Servers</option>
            {servers.map((srv) => (
              <option key={srv.id} value={srv.id}>
                {srv.name} ({srv.location}) -{" "}
                {SERVER_STATUS_CONFIG[srv.status]?.label || srv.status}
              </option>
            ))}
          </select>
        </div>

        {/* Status filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-white/50">Status:</span>
          <select
            value={status}
            onChange={(e) => onStatusChange(e.target.value)}
            className="text-xs bg-white/[0.04] border border-white/10 rounded-lg px-3 py-1.5 text-white/80 focus:outline-none focus:border-sky-400/50 focus:ring-1 focus:ring-sky-400/25"
          >
            <option value="">All Statuses</option>
            {Object.entries(STATUS_CONFIG).map(([key, config]) => (
              <option key={key} value={key}>
                {config.label}
              </option>
            ))}
          </select>
        </div>

        {/* Clear filters */}
        {hasFilters && (
          <button
            onClick={() => {
              onCategoryChange("");
              onServerChange("");
              onStatusChange("");
            }}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs text-white/50 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
          >
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
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
            Clear filters
          </button>
        )}

        {/* Result count */}
        {searched && (
          <div className="ml-auto text-xs text-white/50">
            <span className="font-semibold text-white/80">{total}</span>{" "}
            {total === 1 ? "result" : "results"} found
          </div>
        )}
      </div>
    </div>
  );
}
