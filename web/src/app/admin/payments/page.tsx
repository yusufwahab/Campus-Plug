"use client";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Field";
import type { components } from "@/lib/api-schema";
import { naira } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

type Row = components["schemas"]["PaymentRow"];

export default function AdminPayments() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const rows = useApiQuery<Row[]>(["admin-payments"], "/admin/payments", { status, page });
  return (
    <>
      <PageHeader title="Payments">
        <div className="w-44">
          <Select label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All</option>
            <option value="initiated">Initiated</option>
            <option value="success">Successful</option>
            <option value="failed">Failed</option>
            <option value="refunded">Refunded</option>
          </Select>
        </div>
      </PageHeader>
      <DataTable
        label="Payments"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.reference}
        page={page}
        onPage={setPage}
        empty={{ title: "No payments yet", body: "Payments appear here when buyers start checkout." }}
        cardTitle="ref"
        columns={[
          { key: "ref", header: "Reference", render: (r) => <span className="break-all font-mono text-xs">{r.reference}</span> },
          { key: "o", header: "Order", render: (r) => r.order_id },
          { key: "p", header: "Provider", render: (r) => r.provider },
          { key: "s", header: "Status", render: (r) => <Badge tone={r.status === "success" ? "verified" : r.status === "failed" ? "danger" : "pending"}>{r.status}</Badge> },
          { key: "a", header: "Amount", render: (r) => naira(r.amount_kobo) },
          { key: "f", header: "Provider fee", render: (r) => naira(r.fee_kobo) },
        ]}
      />
    </>
  );
}
