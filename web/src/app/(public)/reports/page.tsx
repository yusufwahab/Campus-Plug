"use client";
import { useQuery } from "@tanstack/react-query";
import { DataTable } from "@/components/admin/DataTable";
import { Badge } from "@/components/ui/Badge";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { RequireAuth } from "@/lib/auth";

type Report = components["schemas"]["ReportMine"];

function Reports() {
  const reports = useQuery({ queryKey: ["my-reports"], queryFn: () => api<Report[]>("/reports") });
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-extrabold">My reports</h1>
      <DataTable
        label="My reports"
        rows={reports.data}
        loading={reports.isPending}
        error={reports.isError ? reports.error.message : null}
        onRetry={() => void reports.refetch()}
        rowKey={(r) => r.id}
        empty={{ title: "You have not reported anything", body: "Use Report on a listing, user, message or review if something is not right." }}
        columns={[
          { key: "t", header: "About", render: (r) => `${r.target_type} ${r.target_id}` },
          { key: "r", header: "Reason", render: (r) => r.reason.replace("_", " ") },
          { key: "s", header: "Status", render: (r) => <Badge tone={r.status === "open" ? "pending" : "verified"}>{r.status}</Badge> },
          { key: "d", header: "Outcome", render: (r) => r.resolution || "Waiting for review" },
          { key: "w", header: "Sent", render: (r) => new Date(r.created_at).toLocaleDateString("en-NG") },
        ]}
      />
    </div>
  );
}

export default function ReportsPage() {
  return (
    <RequireAuth>
      <Reports />
    </RequireAuth>
  );
}
