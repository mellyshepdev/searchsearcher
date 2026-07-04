export type ItemCategory =
  | "log"
  | "container"
  | "app"
  | "program"
  | "document"
  | "config"
  | "metric"
  | "alert"
  | "service"
  | "database";

export type ItemStatus =
  | "active"
  | "inactive"
  | "error"
  | "warning"
  | "stopped"
  | "pending"
  | "completed"
  | "failed";

export type ServerStatus =
  | "online"
  | "offline"
  | "maintenance"
  | "degraded";

export interface SearchResult {
  id: number;
  category: ItemCategory;
  title: string;
  content: string | null;
  metadata: Record<string, unknown> | null;
  status: ItemStatus | null;
  severity: string | null;
  source: string | null;
  tags: string[] | null;
  createdAt: string;
  serverId: number;
  serverName: string;
  serverHostname: string;
  serverLocation: string;
}

export interface ServerInfo {
  id: number;
  name: string;
  hostname: string;
  ipAddress: string;
  location: string;
  status: ServerStatus;
  os: string | null;
  tags: string[] | null;
  itemCount: number;
}

export interface StatsData {
  totalItems: number;
  categoryCounts: Record<string, number>;
  statusCounts: Record<string, number>;
  serverCounts: {
    id: number;
    name: string;
    status: ServerStatus;
    count: number;
  }[];
  severityCounts: Record<string, number>;
}

export const CATEGORY_CONFIG: Record<
  ItemCategory,
  { label: string; icon: string; color: string; bgColor: string }
> = {
  log: {
    label: "Logs",
    icon: "📋",
    color: "text-amber-300",
    bgColor: "bg-amber-400/10 border-amber-400/25",
  },
  container: {
    label: "Containers",
    icon: "🐳",
    color: "text-sky-300",
    bgColor: "bg-sky-400/10 border-sky-400/25",
  },
  app: {
    label: "Applications",
    icon: "🚀",
    color: "text-emerald-300",
    bgColor: "bg-emerald-400/10 border-emerald-400/25",
  },
  program: {
    label: "Programs",
    icon: "⚙️",
    color: "text-purple-300",
    bgColor: "bg-purple-400/10 border-purple-400/25",
  },
  document: {
    label: "Documents",
    icon: "📄",
    color: "text-sky-300",
    bgColor: "bg-sky-400/10 border-sky-400/25",
  },
  config: {
    label: "Configs",
    icon: "🔧",
    color: "text-white/70",
    bgColor: "bg-white/[0.06] border-white/15",
  },
  metric: {
    label: "Metrics",
    icon: "📊",
    color: "text-cyan-300",
    bgColor: "bg-cyan-400/10 border-cyan-400/25",
  },
  alert: {
    label: "Alerts",
    icon: "🔔",
    color: "text-red-300",
    bgColor: "bg-red-400/10 border-red-400/25",
  },
  service: {
    label: "Services",
    icon: "🔌",
    color: "text-indigo-300",
    bgColor: "bg-indigo-400/10 border-indigo-400/25",
  },
  database: {
    label: "Databases",
    icon: "🗄️",
    color: "text-orange-300",
    bgColor: "bg-orange-400/10 border-orange-400/25",
  },
};

export const STATUS_CONFIG: Record<
  ItemStatus,
  { label: string; color: string; dotColor: string }
> = {
  active: {
    label: "Active",
    color: "text-emerald-300 bg-emerald-400/10",
    dotColor: "bg-emerald-400",
  },
  inactive: {
    label: "Inactive",
    color: "text-white/60 bg-white/[0.06]",
    dotColor: "bg-white/40",
  },
  error: {
    label: "Error",
    color: "text-red-300 bg-red-400/10",
    dotColor: "bg-red-400",
  },
  warning: {
    label: "Warning",
    color: "text-amber-300 bg-amber-400/10",
    dotColor: "bg-amber-400",
  },
  stopped: {
    label: "Stopped",
    color: "text-white/70 bg-white/[0.06]",
    dotColor: "bg-white/50",
  },
  pending: {
    label: "Pending",
    color: "text-sky-300 bg-sky-400/10",
    dotColor: "bg-sky-400",
  },
  completed: {
    label: "Completed",
    color: "text-emerald-300 bg-emerald-400/10",
    dotColor: "bg-emerald-500",
  },
  failed: {
    label: "Failed",
    color: "text-red-300 bg-red-400/10",
    dotColor: "bg-red-500",
  },
};

export const SERVER_STATUS_CONFIG: Record<
  ServerStatus,
  { label: string; color: string; dotColor: string }
> = {
  online: {
    label: "Online",
    color: "text-emerald-300 bg-emerald-400/10",
    dotColor: "bg-emerald-400",
  },
  offline: {
    label: "Offline",
    color: "text-white/60 bg-white/[0.06]",
    dotColor: "bg-white/40",
  },
  maintenance: {
    label: "Maintenance",
    color: "text-amber-300 bg-amber-400/10",
    dotColor: "bg-amber-400",
  },
  degraded: {
    label: "Degraded",
    color: "text-orange-300 bg-orange-400/10",
    dotColor: "bg-orange-400",
  },
};
