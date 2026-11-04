"use client";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader, SearchBar } from "@/components/admin/PageHeader";
import type { components } from "@/lib/api-schema";
import { useApiQuery, useDebounced } from "@/lib/hooks";

type Page = components["schemas"]["LogPage"];

export default function ActivityLog() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const search = useDebounced(q);
  const log = useApiQuery<Page>(["activity-log"], "/admin/activity-log", { q: search, page, size: 25 });

  return (
    <>
      <PageHeader title="Activity log" />
      <p className="mb-3 text-sm text-muted">Every Admin action: who did it, when, what changed and why. Entries cannot be edited or deleted.</p>
      <SearchBar value={q} onChange={(v) => { setQ(v); setPage(1); }} label="Search reason or target" />
      <DataTable
        label="Activity log"
        rows={log.data?.items}
        loading={log.isPending}
        error={log.isError ? log.error.message : null}
        onRetry={() => void log.refetch()}
        rowKey={(r) => r.id}
        page={page}
        pageSize={25}
        total={log.data?.total}
        onPage={setPage}
        empty={{ title: "No activity yet", body: "Admin actions are recorded here." }}
        cardTitle="action"
        columns={[
          { key: "when", header: "When", render: (r) => new Date(r.created_at).toLocaleString("en-NG") },
          { key: "action", header: "Action", render: (r) => r.action },
          { key: "who", header: "By", render: (r) => (r.actor_id ? `User #${r.actor_id}` : "System") },
          { key: "target", header: "Target", render: (r) => `${r.target_type} ${r.target_id}` },
          { key: "reason", header: "Reason", render: (r) => r.reason },
        ]}
      />
    </>
  );
}
