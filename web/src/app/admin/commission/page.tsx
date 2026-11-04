"use client";
import { PageHeader } from "@/components/admin/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import type { components } from "@/lib/api-schema";
import { naira } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

type Commission = components["schemas"]["CommissionOut"];
type Revenue = components["schemas"]["RevenueOut"];

export default function AdminCommission() {
  const commission = useApiQuery<Commission>(["admin-commission"], "/admin/commission");
  const revenue = useApiQuery<Revenue>(["admin-revenue"], "/admin/revenue");
  if (commission.isPending || revenue.isPending) return <Skeleton className="h-64" />;
  if (commission.isError || revenue.isError) return <ErrorState message="Could not load commission." onRetry={() => { void commission.refetch(); void revenue.refetch(); }} />;
  const c = commission.data;
  const r = revenue.data;
  const tiles: [string, string][] = [
    ["Commission earned", naira(c.commission_earned_kobo)],
    ["Payment provider fees", naira(c.provider_fees_kobo)],
    ["Campaign discounts paid", naira(c.promo_cost_kobo)],
    ["Sales through the app", naira(r.gmv_kobo)],
    ["Held in escrow", naira(r.held_in_escrow_kobo)],
    ["Owed to sellers", naira(r.owed_to_sellers_kobo)],
    ["Refunded to buyers", naira(r.refunded_kobo)],
    ["Orders paid / confirmed", `${r.orders_paid} / ${r.orders_confirmed}`],
  ];
  return (
    <>
      <PageHeader title="Commission and revenue">
        <Button href="/admin/settings" variant="tertiary">Change rates in Settings</Button>
      </PageHeader>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {tiles.map(([label, value]) => (
          <Card key={label}>
            <p className="text-sm text-muted">{label}</p>
            <p className="font-heading text-2xl font-extrabold">{value}</p>
          </Card>
        ))}
      </div>
      <Card className="mt-4 space-y-2">
        <h2 className="text-lg font-bold">Rules in force for new orders</h2>
        <p>Default commission: <strong>{c.default_bps / 100}%</strong> of the item price after seller discounts, never on delivery fees.</p>
        <p>Payment provider fee is paid by: <strong>{c.provider_fee_absorbed ? "Campus Plug (out of commission)" : "the seller"}</strong>.</p>
        <p>Funds: <strong>{c.instant_split ? "instant split (seller paid at payment time)" : "held until the buyer confirms delivery"}</strong>.</p>
        <p className="text-sm text-muted">Rate changes apply to new orders only. Existing orders keep the rate they were created with. Precedence: seller override, then plan, then category, then default.</p>
      </Card>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-lg font-bold">Category overrides</h2>
          {c.categories.length ? <ul className="space-y-1 text-sm">{c.categories.map((x) => <li key={String(x.name)}>{String(x.name)}: {Number(x.bps) / 100}%</li>)}</ul> : <p className="text-sm text-muted">None. Set them on the Categories page.</p>}
        </Card>
        <Card>
          <h2 className="mb-2 text-lg font-bold">Seller overrides</h2>
          {c.sellers.length ? <ul className="space-y-1 text-sm">{c.sellers.map((x) => <li key={String(x.public_id)}>{String(x.name)} ({String(x.public_id)}): {Number(x.bps) / 100}%</li>)}</ul> : <p className="text-sm text-muted">None. Set them on the Sellers page.</p>}
        </Card>
      </div>
    </>
  );
}
