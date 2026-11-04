"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ProtectionBadge, StatusBadge } from "@/components/orders/parts";
import type { Order } from "@/components/orders/parts";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import { naira, timeAgo } from "@/lib/format";

export default function SellerOrders() {
  const orders = useQuery({ queryKey: ["seller-orders"], queryFn: () => api<Order[]>("/seller/orders"), refetchInterval: 15000 });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-extrabold md:text-3xl">Orders</h1>
      {orders.isPending && <div role="status" aria-label="Loading" className="space-y-2">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-24" />)}</div>}
      {orders.isError && <ErrorState message={orders.error.message} onRetry={() => void orders.refetch()} />}
      {orders.data && !orders.data.length && <EmptyState title="No orders yet" body="Paid orders from buyers appear here. Share your shop to get your first one." action={{ label: "View your shop", href: "/seller" }} />}
      {orders.data && orders.data.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2">
          {orders.data.map((o) => (
            <li key={o.public_id}>
              <Link href={`/seller/orders/${o.public_id}`} className="block rounded-card focus-visible:outline-offset-4">
                <Card className="space-y-2 hover:border-ink">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{o.public_id}</span>
                    <StatusBadge status={o.status} />
                    <ProtectionBadge order={o} />
                    {o.actions.includes("accept") && <span className="rounded-full bg-lime px-2 py-0.5 text-xs font-bold">Needs you</span>}
                  </div>
                  <p className="font-semibold">{o.listing_title}</p>
                  <p className="flex justify-between text-sm text-muted">
                    <span>{o.other_party} · {timeAgo(o.created_at)}</span>
                    <span className="font-heading text-base font-bold text-ink">{naira(o.seller_amount_kobo ?? 0)}</span>
                  </p>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
