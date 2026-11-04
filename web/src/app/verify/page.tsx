"use client";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import type { components } from "@/lib/api-schema";
import { useApiQuery } from "@/lib/hooks";

type Row = components["schemas"]["SubmissionOut"];

export default function VerifyQueue() {
  const [status, setStatus] = useState("pending");
  const rows = useApiQuery<Row[]>(["verify-queue"], "/verify/queue", { status });
  return (
    <>
      <PageHeader title="Verification queue">
        <div className="w-44">
          <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="pending">Pending</option>
            <option value="changes_requested">Changes requested</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </Select>
        </div>
      </PageHeader>
      <DataTable
        label="Assigned submissions"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.id}
        empty={{ title: "Nothing assigned to you", body: "When an Admin assigns a seller to you it appears here." }}
        columns={[
          { key: "shop", header: "Shop", render: (r) => r.shop_name },
          { key: "id", header: "Seller ID", render: (r) => r.shop_public_id },
          { key: "kind", header: "Type", render: (r) => (r.kind === "identity" ? "Identity" : "Payout review") },
          { key: "status", header: "Status", render: (r) => <Badge tone={r.status === "pending" ? "pending" : r.status === "approved" ? "verified" : "danger"}>{r.status.replace("_", " ")}</Badge> },
        ]}
        actions={(r) => <Button variant="secondary" href={`/verify/${r.id}`}>{r.status === "pending" ? "Review" : "View"}</Button>}
      />
    </>
  );
}
