"use client";
import { useParams } from "next/navigation";
import { PageHeader } from "@/components/admin/PageHeader";
import { ProtectionBadge, Row, StatusBadge, Timeline } from "@/components/orders/parts";
import type { Order } from "@/components/orders/parts";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { naira } from "@/lib/format";
import { useApiQuery } from "@/lib/hooks";

export default function AdminOrderDetail() {
  const { id } = useParams<{ id: string }>();
  const order = useApiQuery<Order>(["admin-order", id], `/admin/orders/${id}`);
  if (order.isPending) return <Skeleton className="h-64" />;
  if (order.isError) return <ErrorState message={order.error.message} onRetry={() => void order.refetch()} />;
  const o = order.data;
  return (
    <>
      <PageHeader title={o.public_id}>
        <StatusBadge status={o.status} />
        <ProtectionBadge order={o} />
        {o.dispute && <Button href="/admin/disputes" variant="tertiary">Dispute {o.dispute.public_id}</Button>}
      </PageHeader>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-lg font-bold">Money</h2>
          <dl>
            <Row label="Item price" value={naira(o.unit_price_kobo * o.quantity)} />
            <Row label="Seller discount" value={naira(o.seller_discount_kobo)} />
            <Row label="Campaign discount (platform paid)" value={naira(o.platform_discount_kobo)} />
            <Row label="Delivery" value={naira(o.delivery_fee_kobo)} />
            <Row label="Buyer paid" value={naira(o.buyer_total_kobo)} />
            <Row label={`Commission (${(o.commission_bps ?? 0) / 100}%, frozen on this order)`} value={naira(o.commission_kobo ?? 0)} />
            <Row label="Provider fee" value={naira(o.provider_fee_kobo ?? 0)} />
            <Row label="Refunded (item)" value={naira(o.refunded_item_kobo)} />
            <Row label="Seller receives" value={naira(o.seller_amount_kobo ?? 0)} strong />
            <Row label="Payout" value={o.payout_status ?? "none"} />
          </dl>
        </Card>
        <Card>
          <h2 className="mb-2 text-lg font-bold">History</h2>
          <Timeline events={o.timeline} />
          <p className="mt-3 text-xs text-muted">{o.listing_id} · {o.listing_type} · {o.fulfilment} · seller {o.other_party}</p>
        </Card>
      </div>
    </>
  );
}
