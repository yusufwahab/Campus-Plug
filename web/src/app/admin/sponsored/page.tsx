"use client";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { naira } from "@/lib/format";
import { useAction, useApiQuery } from "@/lib/hooks";

type Row = { id: number; listing_id: string; shop_name: string; days: number; price_kobo: number; status: string; ends_at: string | null; payment: string };
type Action = "approve" | "reject" | "pause" | "resume";

const verbs: Record<Action, string> = { approve: "Approve", reject: "Reject and refund", pause: "Pause", resume: "Resume" };

function available(status: string): Action[] {
  if (status === "pending") return ["approve", "reject"];
  if (status === "active") return ["pause", "reject"];
  if (status === "paused") return ["resume", "reject"];
  return [];
}

export default function AdminSponsored() {
  const rows = useApiQuery<Row[]>(["admin-sponsored"], "/admin/sponsored");
  const act = useAction([["admin-sponsored"]]);
  const [target, setTarget] = useState<{ row: Row; action: Action } | null>(null);

  return (
    <>
      <PageHeader title="Sponsored placements" />
      <p className="mb-3 max-w-prose text-sm text-muted">Sellers pay for a boost first. Approve it to put the listing at the top of search with a Sponsored label. Rejecting refunds the seller.</p>
      <DataTable
        label="Boosts"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.id}
        empty={{ title: "No boosts yet", body: "Paid boosts waiting for approval appear here." }}
        columns={[
          { key: "l", header: "Listing", render: (r) => r.listing_id },
          { key: "s", header: "Shop", render: (r) => r.shop_name },
          { key: "d", header: "Length", render: (r) => `${r.days} days, ${naira(r.price_kobo)}` },
          { key: "st", header: "Status", render: (r) => <Badge tone={r.status === "active" ? "verified" : r.status === "pending" ? "pending" : "neutral"}>{r.payment === "refunded" ? "refunded" : r.status}</Badge> },
        ]}
        actions={(r) => (
          <>
            {available(r.status).map((a) => (
              <Button key={a} variant={a === "reject" ? "danger" : "tertiary"} onClick={() => setTarget({ row: r, action: a })}>
                {verbs[a]}
              </Button>
            ))}
          </>
        )}
      />
      {target && (
        <ReasonModal
          open
          title={`${verbs[target.action]} boost for ${target.row.listing_id}?`}
          confirmLabel={verbs[target.action]}
          destructive={target.action === "reject"}
          onConfirm={(reason) => act("POST", `/admin/sponsored/${target.row.id}/action`, { action: target.action, reason }, "Boost updated").then(() => undefined)}
          onClose={() => setTarget(null)}
        />
      )}
    </>
  );
}
