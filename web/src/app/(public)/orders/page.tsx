"use client";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import Link from "next/link";
import { useState } from "react";
import { ProtectionBadge, StatusBadge } from "@/components/orders/parts";
import type { Order } from "@/components/orders/parts";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";
import { naira, timeAgo } from "@/lib/format";

const tabs = [
  { id: "active", label: "Active", match: (o: Order) => ["pending_payment", "paid", "accepted", "preparing", "ready", "delivered", "disputed"].includes(o.status) },
  { id: "done", label: "Completed", match: (o: Order) => ["confirmed", "paid_out"].includes(o.status) },
  { id: "closed", label: "Cancelled", match: (o: Order) => ["cancelled", "refunded"].includes(o.status) },
] as const;

function Orders() {
  const [tab, setTab] = useState<(typeof tabs)[number]["id"]>("active");
  const orders = useQuery({ queryKey: ["orders"], queryFn: () => api<Order[]>("/orders"), refetchInterval: 20000 });
  const current = tabs.find((t) => t.id === tab)!;
  const shown = orders.data?.filter(current.match);

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-extrabold">Orders</h1>
      <div role="tablist" aria-label="Order groups" className="flex gap-2 overflow-x-auto">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)} className={clsx("min-h-11 shrink-0 rounded-full px-5 text-sm font-semibold", tab === t.id ? "bg-ink text-white" : "border border-line bg-white")}>
            {t.label}
            {orders.data && <span className="ml-1 text-xs opacity-70">({orders.data.filter(t.match).length})</span>}
          </button>
        ))}
      </div>
      {orders.isPending && <div role="status" aria-label="Loading" className="space-y-2">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-24" />)}</div>}
      {orders.isError && <ErrorState message={orders.error.message} onRetry={() => void orders.refetch()} />}
      {shown && !shown.length && <EmptyState title={`No ${current.label.toLowerCase()} orders`} body="When you buy or book something it shows up here." action={{ label: "Browse listings", href: "/search" }} />}
      {shown && shown.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2">
          {shown.map((o) => (
            <li key={o.public_id}>
              <Link href={o.status === "pending_payment" ? `/checkout/${o.public_id}` : `/orders/${o.public_id}`} className="block rounded-card focus-visible:outline-offset-4">
                <Card className="space-y-2 hover:border-ink">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{o.public_id}</span>
                    <StatusBadge status={o.status} />
                    <ProtectionBadge order={o} />
                  </div>
                  <p className="font-semibold">{o.listing_title}</p>
                  <p className="flex justify-between text-sm text-muted">
                    <span>{o.other_party} · {timeAgo(o.created_at)}</span>
                    <span className="font-heading text-base font-bold text-ink">{naira(o.buyer_total_kobo)}</span>
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

export default function OrdersPage() {
  return (
    <RequireAuth>
      <Orders />
    </RequireAuth>
  );
}
