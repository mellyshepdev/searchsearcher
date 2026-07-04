"use client";

import {
  CATEGORY_CONFIG,
  SERVER_STATUS_CONFIG,
} from "@/types/search";
import type { StatsData, ServerInfo, ItemCategory, ServerStatus } from "@/types/search";

interface StatsPanelProps {
  stats: StatsData;
  servers: ServerInfo[];
}

export default function StatsPanel({ stats, servers }: StatsPanelProps) {
  const categoryEntries = Object.entries(stats.categoryCounts)
    .sort(([, a], [, b]) => b - a)
    .filter(([, count]) => count > 0);

  const maxCategoryCount = Math.max(
    ...categoryEntries.map(([, count]) => count),
    1
  );

  return (
    <div className="sticky top-20 space-y-4">
      {/* Total items */}
      <div className="bg-white/[0.04] backdrop-blur-xl rounded-xl border border-white/10 p-4">
        <div className="text-center">
          <div className="text-3xl font-bold text-white">
            {stats.totalItems.toLocaleString()}
          </div>
          <div className="text-xs text-white/50 mt-0.5">
            searchable items
          </div>
        </div>
        <div className="mt-3 flex items-center justify-center gap-3 text-[11px]">
          {Object.entries(stats.severityCounts).map(([sev, count]) => (
            <span
              key={sev}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-medium ${
                sev === "critical"
                  ? "bg-red-400/15 text-red-300"
                  : sev === "high"
                  ? "bg-orange-400/15 text-orange-300"
                  : sev === "medium"
                  ? "bg-amber-400/15 text-amber-300"
                  : "bg-sky-400/15 text-sky-300"
              }`}
            >
              {sev}: {count}
            </span>
          ))}
        </div>
      </div>

      {/* Server Status */}
      <div className="bg-white/[0.04] backdrop-blur-xl rounded-xl border border-white/10 p-4">
        <h4 className="text-xs font-semibold text-white/60 uppercase tracking-wider mb-3">
          Servers
        </h4>
        <div className="space-y-2.5">
          {stats.serverCounts.map((srv) => {
            const srvConfig = SERVER_STATUS_CONFIG[srv.status as ServerStatus];
            return (
              <div key={srv.id} className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    srvConfig?.dotColor || "bg-white/30"
                  }`}
                  title={srvConfig?.label || srv.status}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-white/70 truncate">
                    {srv.name}
                  </div>
                </div>
                <span className="text-[11px] text-white/50 font-mono">
                  {srv.count}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Category Breakdown */}
      <div className="bg-white/[0.04] backdrop-blur-xl rounded-xl border border-white/10 p-4">
        <h4 className="text-xs font-semibold text-white/60 uppercase tracking-wider mb-3">
          By Category
        </h4>
        <div className="space-y-2">
          {categoryEntries.map(([cat, count]) => {
            const config = CATEGORY_CONFIG[cat as ItemCategory];
            if (!config) return null;
            const percent = (count / maxCategoryCount) * 100;
            return (
              <div key={cat}>
                <div className="flex items-center justify-between mb-0.5">
                  <span className="inline-flex items-center gap-1.5 text-xs text-white/60">
                    <span>{config.icon}</span>
                    {config.label}
                  </span>
                  <span className="text-[11px] font-semibold text-white/70">
                    {count}
                  </span>
                </div>
                <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-sky-500 to-sky-400 rounded-full transition-all duration-500"
                    style={{ width: `${percent}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Status Overview */}
      <div className="bg-white/[0.04] backdrop-blur-xl rounded-xl border border-white/10 p-4">
        <h4 className="text-xs font-semibold text-white/60 uppercase tracking-wider mb-3">
          Status Overview
        </h4>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(stats.statusCounts)
            .filter(([, count]) => count > 0)
            .sort(([, a], [, b]) => b - a)
            .map(([st, count]) => {
              const statusColors: Record<string, string> = {
                active: "border-emerald-400/25 bg-emerald-400/10",
                warning: "border-amber-400/25 bg-amber-400/10",
                error: "border-red-400/25 bg-red-400/10",
                completed: "border-sky-400/25 bg-sky-400/10",
                inactive: "border-white/10 bg-white/[0.04]",
                stopped: "border-white/10 bg-white/[0.04]",
                pending: "border-sky-400/25 bg-sky-400/10",
                failed: "border-red-400/25 bg-red-400/10",
              };
              return (
                <div
                  key={st}
                  className={`rounded-lg border p-2 text-center ${
                    statusColors[st] || "border-white/10 bg-white/[0.04]"
                  }`}
                >
                  <div className="text-lg font-bold text-white/85">
                    {count}
                  </div>
                  <div className="text-[10px] text-white/50 capitalize">
                    {st}
                  </div>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
