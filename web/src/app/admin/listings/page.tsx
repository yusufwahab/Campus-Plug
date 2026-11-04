"use client";
import Link from "next/link";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader, SearchBar } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { components } from "@/lib/api-schema";
import { naira } from "@/lib/format";
import { useAction, useApiQuery, useDebounced } from "@/lib/hooks";

type Row = components["schemas"]["AdminListing"];

export default function AdminListings() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const search = useDebounced(q);
  const rows = useApiQuery<Row[]>(["admin-listings"], "/admin/listings", { q: search, page });
  const act = useAction([["admin-listings"]]);
  const [target, setTarget] = useState<{ row: Row; action: "remove" | "restore" } | null>(null);

  return (
    <>
      <PageHeader title="Listings" />
      <SearchBar value={q} onChange={(v) => { setQ(v); setPage(1); }} label="Search title or CP-P / CP-S ID" />
      <DataTable
        label="Listings"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.public_id}
        page={page}
        onPage={setPage}
        empty={{ title: "No listings match", body: "Search by title or listing ID." }}
        columns={[
          { key: "t", header: "Listing", render: (r) => <Link className="font-semibold underline" href={`/listing/${r.public_id}`}>{r.title}</Link> },
          { key: "id", header: "ID", render: (r) => r.public_id },
          { key: "shop", header: "Seller", render: (r) => r.shop_name },
          { key: "price", header: "Price", render: (r) => naira(r.price_kobo) },
          { key: "s", header: "Status", render: (r) => <Badge tone={r.status === "active" ? "verified" : r.status === "removed" ? "danger" : "neutral"}>{r.status.replace("_", " ")}</Badge> },
        ]}
        actions={(r) =>
          r.status === "removed" ? (
            <Button variant="tertiary" onClick={() => setTarget({ row: r, action: "restore" })}>Restore</Button>
          ) : (
            <Button variant="danger" onClick={() => setTarget({ row: r, action: "remove" })}>Remove</Button>
          )
        }
      />
      {target && (
        <ReasonModal
          open
          title={target.action === "remove" ? `Remove ${target.row.public_id}?` : `Restore ${target.row.public_id}?`}
          description={target.action === "remove" ? "The listing disappears from the marketplace. The seller keeps the record." : "The listing returns as paused so the seller can review it before resuming."}
          confirmLabel={target.action === "remove" ? "Remove listing" : "Restore listing"}
          destructive={target.action === "remove"}
          onConfirm={(reason) => act("POST", `/admin/listings/${target.row.public_id}/moderate`, { action: target.action, reason }, "Listing updated").then(() => undefined)}
          onClose={() => setTarget(null)}
        />
      )}
    </>
  );
}
