"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { DataTable } from "@/components/admin/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { naira } from "@/lib/format";

type Earnings = components["schemas"]["EarningsOut"];

export default function SellerEarnings() {
  const earnings = useQuery({ queryKey: ["earnings"], queryFn: () => api<Earnings>("/seller/earnings"), refetchInterval: 30000 });
  if (earnings.isPending) return <div role="status" aria-label="Loading" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-24" />)}</div>;
  if (earnings.isError) return <ErrorState message={earnings.error.message} onRetry={() => void earnings.refetch()} />;
  const e = earnings.data;
  const tiles: [string, number, string?][] = [
    ["Gross sales", e.gross_sales_kobo],
    ["Discounts you gave", e.discounts_kobo],
    ["Campus Plug commission", e.commission_kobo],
    ["Net earnings", e.net_earnings_kobo, "Sales after commission"],
    ["Held funds", e.held_kobo, "Paid by buyers, waiting for delivery confirmation"],
    ["Payouts processing", e.processing_payouts_kobo],
    ["Paid out", e.paid_payouts_kobo],
  ];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-extrabold md:text-3xl">Earnings</h1>
      {e.unverified && (
        <p className="rounded-card bg-pending-bg p-4 text-sm text-pending-fg">
          You are not verified, so buyers cannot pay you in the app. <Link href="/seller/verification" className="font-semibold underline">Verify your identity</Link> to start receiving in-app payments.
        </p>
      )}
      {e.payout_review_required && <p className="rounded-card bg-pending-bg p-4 text-sm text-pending-fg">Your payout details are under review. Payouts resume once they are approved.</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map(([label, value, hint]) => (
          <Card key={label}>
            <p className="text-sm text-muted">{label}</p>
            <p className="font-heading text-3xl font-extrabold">{naira(value)}</p>
            {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
          </Card>
        ))}
      </div>
      <h2 className="text-lg font-bold">Payouts</h2>
      <DataTable
        label="Payouts"
        rows={e.payouts as { order: string; amount_kobo: number; status: string; hold_reason: string; created_at: string }[]}
        rowKey={(p) => `${p.order}-${p.created_at}`}
        empty={{ title: "No payouts yet", body: "When a buyer confirms delivery, your payout appears here." }}
        columns={[
          { key: "o", header: "Order", render: (p) => <Link className="font-semibold underline" href={`/seller/orders/${p.order}`}>{p.order}</Link> },
          { key: "a", header: "Amount", render: (p) => naira(p.amount_kobo) },
          { key: "s", header: "Status", render: (p) => <Badge tone={p.status === "paid" ? "verified" : p.status === "held" ? "danger" : "pending"}>{p.status}</Badge> },
          { key: "h", header: "Note", render: (p) => p.hold_reason || "None" },
          { key: "d", header: "Date", render: (p) => new Date(p.created_at).toLocaleDateString("en-NG") },
        ]}
      />
    </div>
  );
}
