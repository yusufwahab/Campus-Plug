"use client";
import Link from "next/link";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader, SearchBar } from "@/components/admin/PageHeader";
import { ProtectionBadge, StatusBadge } from "@/components/orders/parts";
import { Select } from "@/components/ui/Field";
import type { components } from "@/lib/api-schema";
import { naira } from "@/lib/format";
import { useApiQuery, useDebounced } from "@/lib/hooks";

type Row = components["schemas"]["OrderRow"];

export default function AdminOrders() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const search = useDebounced(q);
  const rows = useApiQuery<Row[]>(["admin-orders"], "/admin/orders", { q: search, status, page });
  return (
    <>
      <PageHeader title="Orders" />
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 basis-56"><SearchBar value={q} onChange={(v) => { setQ(v); setPage(1); }} label="Search order ID (CP-O-…), item or shop" /></div>
        <div className="w-full md:w-52">
          <Select label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {["pending_payment", "paid", "accepted", "preparing", "ready", "delivered", "confirmed", "paid_out", "cancelled", "refunded", "disputed"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </Select>
        </div>
      </div>
      <DataTable
        label="Orders"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.public_id}
        page={page}
        onPage={setPage}
        empty={{ title: "No orders match", body: "Search by an order ID like CP-O-90001, an item or a shop." }}
        columns={[
          { key: "id", header: "Order", render: (r) => <Link className="font-semibold underline" href={`/admin/orders/${r.public_id}`}>{r.public_id}</Link> },
          { key: "i", header: "Item", render: (r) => r.listing_title },
          { key: "s", header: "Shop", render: (r) => r.shop_name },
          { key: "st", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
          { key: "p", header: "Protection", render: (r) => <ProtectionBadge order={r} /> },
          { key: "t", header: "Buyer paid", render: (r) => naira(r.buyer_total_kobo) },
          { key: "c", header: "Commission", render: (r) => naira(r.commission_kobo) },
        ]}
      />
    </>
  );
}
