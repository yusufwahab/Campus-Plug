"use client";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import type { components } from "@/lib/api-schema";
import { naira } from "@/lib/format";
import { useAction, useApiQuery } from "@/lib/hooks";

type Row = components["schemas"]["PayoutRow"];

export default function AdminPayouts() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const rows = useApiQuery<Row[]>(["admin-payouts"], "/admin/payouts", { status, page });
  const act = useAction([["admin-payouts"]]);
  const [target, setTarget] = useState<{ row: Row; action: "release" | "hold" } | null>(null);
  return (
    <>
      <PageHeader title="Payouts">
        <div className="w-44">
          <Select label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="held">Held</option>
            <option value="processing">Processing</option>
            <option value="paid">Paid</option>
          </Select>
        </div>
      </PageHeader>
      <DataTable
        label="Payouts"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.id}
        page={page}
        onPage={setPage}
        empty={{ title: "No payouts yet", body: "Payouts are created when a buyer confirms delivery." }}
        columns={[
          { key: "o", header: "Order", render: (r) => r.order_id },
          { key: "s", header: "Seller", render: (r) => r.shop_name },
          { key: "a", header: "Amount", render: (r) => naira(r.amount_kobo) },
          { key: "st", header: "Status", render: (r) => <Badge tone={r.status === "paid" ? "verified" : r.status === "held" ? "danger" : "pending"}>{r.status}</Badge> },
          { key: "h", header: "Note", render: (r) => r.hold_reason || "None" },
        ]}
        actions={(r) =>
          r.status === "held" ? <Button variant="secondary" onClick={() => setTarget({ row: r, action: "release" })}>Release</Button> : r.status === "pending" ? <Button variant="tertiary" onClick={() => setTarget({ row: r, action: "hold" })}>Hold</Button> : null
        }
      />
      {target && (
        <ReasonModal
          open
          title={target.action === "release" ? `Release payout for ${target.row.order_id}?` : `Hold payout for ${target.row.order_id}?`}
          description={target.action === "release" ? `${naira(target.row.amount_kobo)} is sent to ${target.row.shop_name}.` : "The payout will not be sent until an Admin releases it."}
          confirmLabel={target.action === "release" ? `Release ${naira(target.row.amount_kobo)}` : "Hold payout"}
          destructive={target.action === "hold"}
          onConfirm={(reason) => act("POST", `/admin/payouts/${target.row.id}/action`, { action: target.action, reason }, target.action === "release" ? "Payout queued" : "Payout held").then(() => undefined)}
          onClose={() => setTarget(null)}
        />
      )}
    </>
  );
}
