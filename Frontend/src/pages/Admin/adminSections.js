import { FileText, HardDrive, LayoutDashboard, ScrollText, ShieldAlert, Users, UsersRound } from "lucide-react";

export const adminNavigation = [
  { to: "/admin", label: "Overview", Icon: LayoutDashboard, end: true },
  { to: "/admin/users", label: "Users", Icon: Users },
  { to: "/admin/study-groups", label: "Study groups", Icon: UsersRound },
  { to: "/admin/attachments", label: "Attachments", Icon: HardDrive },
  { to: "/admin/reports", label: "Reports", Icon: ShieldAlert },
  { to: "/admin/system-logs", label: "System logs", Icon: ScrollText },
];

export function formatDate(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleString();
}

export function formatSize(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  const bytes = Number(value);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const adminCollections = {
  users: {
    title: "User management",
    description: "Search and inspect registered accounts. Account changes require backend governance support.",
    columns: [
      ["Name", "full_name"], ["Email", "email"], ["Role", "role", "status"],
      ["Status", "status", "status"], ["Last active", "last_active_at", "date"],
    ],
  },
  "study-groups": {
    title: "Study groups",
    description: "Group ownership, visibility, and activity metadata; no private chat content.",
    columns: [
      ["Group", "name"], ["Owner", "owner_name"], ["Visibility", "visibility", "status"],
      ["Members", "member_count"], ["Status", "status", "status"],
    ],
  },
  attachments: {
    title: "Notes & attachments",
    description: "Uploaded content metadata and processing status. No private files are exposed here.",
    columns: [
      ["File", "file_name"], ["Uploaded by", "uploader_name"], ["Source", "source"],
      ["Size", "file_size_bytes", "size"], ["Status", "status", "status"],
      ["Uploaded", "uploaded_at", "date"],
    ],
  },
  reports: {
    title: "Reports",
    description: "Privacy-preserving report queue; review and resolution workflows will follow.",
    columns: [
      ["Target", "target_description"], ["Category", "category"],
      ["Target type", "target_type"], ["Status", "status", "status"],
      ["Submitted", "created_at", "date"],
    ],
  },
  "system-logs": {
    title: "System logs",
    description: "Read-only sanitized system events with severity, service, and time filters.",
    columns: [
      ["Time", "occurred_at", "date"], ["Severity", "severity", "status"],
      ["Service", "service"], ["Message", "message"], ["Request ID", "request_id"],
    ],
  },
};

export const summaryCards = [
  { label: "Active users", key: "active_users", Icon: Users, to: "/admin/users" },
  { label: "Study groups", key: "active_study_groups", Icon: UsersRound, to: "/admin/study-groups" },
  { label: "Stored notes", key: "stored_notes", Icon: FileText, to: "/admin/attachments" },
  { label: "Processing failures (24h)", key: "processing_failures_24h", Icon: HardDrive, to: "/admin/attachments" },
  { label: "Open reports", key: "open_reports", Icon: ShieldAlert, to: "/admin/reports" },
  { label: "Under review", key: "under_review_reports", Icon: ShieldAlert, to: "/admin/reports" },
];
