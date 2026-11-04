"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/lib/api-schema";

type Overview = components["schemas"]["SellerOverview"];

export default function SellerOverview() {
  const client = useQueryClient();
  const toast = useToast();
  const overview = useQuery({ queryKey: ["seller-overview"], queryFn: () => api<Overview>("/seller/overview"), retry: false });

  if (overview.isPending) return <div role="status" aria-label="Loading" className="space-y-3"><Skeleton className="h-8 w-1/3" /><Skeleton className="h-48" /></div>;
  if (overview.error instanceof ApiError && overview.error.status === 404) {
    return <EmptyState title="Set up your shop" body="Create your shop to see earnings, orders and tasks here." action={{ label: "Open your shop", href: "/seller/start" }} />;
  }
  if (overview.isError) return <ErrorState message={overview.error.message} onRetry={() => void overview.refetch()} />;

  const o = overview.data;
  const done = o.checklist.filter((c) => c.done).length;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-extrabold md:text-3xl">Seller overview</h1>
        <Badge tone={o.shop.verification_status === "verified" ? "verified" : "pending"}>{o.shop.verification_status === "verified" ? "Verified" : "Unverified"}</Badge>
        <span className="text-xs text-muted">{o.shop.public_id}</span>
      </div>

      {!o.rules_accepted && (
        <Card className="space-y-2 border-pending-fg bg-pending-bg">
          <h2 className="text-lg font-bold text-pending-fg">Accept the seller rules to start listing</h2>
          <p className="text-sm text-pending-fg">A Hall Rep opened this shop for you. Read the <Link href="/seller-rules" className="font-semibold underline">seller rules</Link>, then accept them.</p>
          <Button onClick={async () => { await api("/seller/accept-rules", { method: "POST" }); await client.invalidateQueries({ queryKey: ["seller-overview"] }); toast("Seller rules accepted"); }}>I accept the seller rules</Button>
        </Card>
      )}

      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">Setup checklist</h2>
          <span className="text-sm text-muted">{done} of {o.checklist.length} done</span>
        </div>
        <ul className="space-y-1">
          {o.checklist.map((c) => (
            <li key={c.key}>
              <Link href={c.href} className="flex min-h-11 items-center gap-3 rounded-input px-2 text-sm font-semibold hover:bg-ground">
                {c.done ? <CheckCircle2 className="size-5 text-forest" aria-label="Done" /> : <Circle className="size-5 text-muted" aria-label="To do" />}
                <span className={c.done ? "text-muted line-through" : ""}>{c.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <p className="text-sm text-muted">Live listings</p>
          <p className="font-heading text-3xl font-extrabold">
            {o.live_listings}
            {o.listing_limit !== null && o.listing_limit !== undefined && <span className="text-base text-muted"> / {o.listing_limit}</span>}
          </p>
          {o.listing_limit !== null && o.listing_limit !== undefined && <p className="mt-1 text-xs text-muted">Verify your identity to list without a limit.</p>}
        </Card>
        <Card>
          <p className="text-sm text-muted">Trust level</p>
          <p className="font-heading text-xl font-extrabold capitalize">{o.shop.trust_level.replace(/_/g, " ")}</p>
        </Card>
        <Card>
          <p className="text-sm text-muted">Confirmed deals</p>
          <p className="font-heading text-3xl font-extrabold">{o.shop.confirmed_deals}</p>
        </Card>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button href="/seller/listings/new">Add a listing</Button>
        <Button href={`/shop/${o.shop.slug}`} variant="tertiary">View public shop</Button>
      </div>
    </div>
  );
}
