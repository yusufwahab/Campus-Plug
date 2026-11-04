import { Badge } from "@/components/ui/Badge";
import type { BadgeTone } from "@/components/ui/Badge";
import type { components } from "@/lib/api-schema";
import { naira } from "@/lib/format";

export type Order = components["schemas"]["OrderOut"];

const labels: Record<string, string> = {
  pending_payment: "Pending payment",
  paid: "Paid",
  accepted: "Accepted",
  preparing: "Preparing",
  ready: "Ready or on its way",
  delivered: "Delivered",
  confirmed: "Confirmed",
  paid_out: "Paid out",
  cancelled: "Cancelled",
  refunded: "Refunded",
  disputed: "Disputed",
};

const tones: Record<string, BadgeTone> = {
  pending_payment: "pending",
  paid: "info",
  accepted: "info",
  preparing: "info",
  ready: "info",
  delivered: "pending",
  confirmed: "verified",
  paid_out: "verified",
  cancelled: "danger",
  refunded: "danger",
  disputed: "danger",
};

export const statusLabel = (s: string) => labels[s] ?? s;

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={tones[status] ?? "neutral"}>{statusLabel(status)}</Badge>;
}

export function ProtectionBadge({ order }: { order: Pick<Order, "protected"> }) {
  return order.protected ? <Badge tone="verified">Protected</Badge> : <Badge tone="pending">Not protected</Badge>;
}

export function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`flex justify-between gap-4 py-1.5 text-sm ${strong ? "border-t border-line pt-3 font-bold" : ""}`}>
      <dt className={strong ? "" : "text-muted"}>{label}</dt>
      <dd className={strong ? "font-heading text-lg" : "font-semibold"}>{value}</dd>
    </div>
  );
}

/** Price breakdown the buyer sees: item, discounts, delivery and final total. Commission is never shown here. */
export function BuyerBreakdown({ o }: { o: Order }) {
  const gross = o.unit_price_kobo * o.quantity;
  return (
    <dl>
      <Row label={`${o.listing_title} × ${o.quantity}`} value={naira(gross)} />
      {o.seller_discount_kobo > 0 && <Row label="Seller discount" value={`-${naira(o.seller_discount_kobo)}`} />}
      {o.platform_discount_kobo > 0 && <Row label="Campaign discount" value={`-${naira(o.platform_discount_kobo)}`} />}
      {o.delivery_fee_kobo > 0 && <Row label="Delivery" value={naira(o.delivery_fee_kobo)} />}
      <Row label={o.deposit_only ? "Deposit to pay now" : "Total"} value={naira(o.buyer_total_kobo)} strong />
    </dl>
  );
}

export function Timeline({ events }: { events: Order["timeline"] }) {
  return (
    <ol className="space-y-2" aria-label="Order history">
      {events.map((e, i) => (
        <li key={`${e.status}-${i}`} className="flex gap-3 text-sm">
          <span aria-hidden="true" className="mt-1.5 size-2.5 shrink-0 rounded-full bg-forest" />
          <span>
            <span className="font-semibold">{statusLabel(e.status)}</span>
            <span className="ml-2 text-xs text-muted">{new Date(e.at).toLocaleString("en-NG")}</span>
            {e.note && <span className="block text-xs text-muted">{e.note}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}
