"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { FormError } from "@/components/auth/AuthCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Field";
import { ConfirmModal, Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api, assetUrl } from "@/lib/api";
import { naira } from "@/lib/format";
import { BuyerBreakdown, ProtectionBadge, Row, StatusBadge, Timeline } from "./parts";
import type { Order } from "./parts";

type Action = "confirm" | "cancel" | "decline" | "accept" | "preparing" | "ready" | "delivered" | "buyer_no_show" | "confirm_offline";

const stageActions = ["preparing", "ready", "delivered"];

/** One order screen for buyers and sellers. What each person can do comes from the backend's `actions` list. */
export function OrderDetail({ id, base }: { id: string; base: "buyer" | "seller" }) {
  const client = useQueryClient();
  const toast = useToast();
  const order = useQuery({ queryKey: ["order", id], queryFn: () => api<Order>(`/orders/${id}`), refetchInterval: 15000 });
  const [confirm, setConfirm] = useState<Action | null>(null);
  const [reason, setReason] = useState("");
  const [respondOpen, setRespondOpen] = useState(false);
  const [response, setResponse] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (order.isPending) return <Skeleton className="h-96" />;
  if (order.isError) return <ErrorState message={order.error.message} onRetry={() => void order.refetch()} />;
  const o = order.data;
  const isBuyer = o.role === "buyer";

  async function run(action: Action) {
    setBusy(true);
    setError(null);
    try {
      if (action === "confirm_offline") await api(`/orders/${id}/confirm-offline`, { method: "POST" });
      else if (action === "buyer_no_show") await api(`/orders/${id}/no-show`, { method: "POST" });
      else if (stageActions.includes(action)) await api(`/orders/${id}/stage`, { method: "POST", body: { stage: action } });
      else await api(`/orders/${id}/${action}`, { method: "POST", body: { reason } });
      await Promise.all([client.invalidateQueries({ queryKey: ["order", id] }), client.invalidateQueries({ queryKey: ["orders"] }), client.invalidateQueries({ queryKey: ["seller-orders"] })]);
      toast(action === "confirm" ? "Delivery confirmed. The seller will be paid." : "Order updated");
      setConfirm(null);
      setReason("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function respond() {
    if (!o.dispute) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/disputes/${o.dispute.public_id}/respond`, { method: "POST", body: { message: response } });
      await client.invalidateQueries({ queryKey: ["order", id] });
      setRespondOpen(false);
      setResponse("");
      toast("Your response was sent");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send your response.");
    } finally {
      setBusy(false);
    }
  }

  const has = (a: string) => o.actions.includes(a);
  const confirmCopy: Partial<Record<Action, { title: string; body: string; label: string; destructive?: boolean; needsReason?: boolean }>> = {
    confirm: { title: "Confirm you received it?", body: "This releases your payment to the seller. Only confirm if you got what you ordered.", label: "Yes, I received it" },
    cancel: { title: "Cancel this order?", body: o.status === "pending_payment" ? "Nothing has been charged." : "You will be refunded in full.", label: "Cancel order", destructive: true, needsReason: true },
    decline: { title: "Decline this order?", body: "The buyer is refunded in full and the order is cancelled.", label: "Decline order", destructive: true, needsReason: true },
    buyer_no_show: { title: "Report a no-show?", body: "The booking time has passed. An Admin will review what happened.", label: "Report no-show", destructive: true },
    confirm_offline: { title: "Confirm this cash deal?", body: "Cash and direct transfer deals are Not protected: Campus Plug cannot refund them. Only confirm once the deal is done.", label: "Confirm deal" },
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4 pb-24">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-extrabold md:text-3xl">{o.listing_title}</h1>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{o.public_id}</span>
        <StatusBadge status={o.status} />
        <ProtectionBadge order={o} />
        {o.booking_at && <Badge tone="info">Booking {new Date(o.booking_at).toLocaleString("en-NG")}</Badge>}
      </div>
      {!o.protected && <p className="rounded-input bg-pending-bg p-3 text-sm text-pending-fg">This is a cash or direct transfer deal. It is Not protected: Campus Plug cannot refund or settle disputes for it.</p>}

      <FormError message={error} />
      <div className="flex flex-wrap gap-2" role="group" aria-label="Order actions">
        {has("pay") && <Button href={`/checkout/${o.public_id}`}>Pay {naira(o.buyer_total_kobo)}</Button>}
        {has("confirm") && <Button onClick={() => setConfirm("confirm")}>I received it</Button>}
        {has("confirm_offline") && <Button onClick={() => setConfirm("confirm_offline")}>Confirm cash deal</Button>}
        {has("problem") && <Button variant="tertiary" href={`/orders/${o.public_id}/problem`}>Report a problem</Button>}
        {o.can_review && <Button variant="secondary" href={`/orders/${o.public_id}/review`}>Leave a review</Button>}
        {has("accept") && <Button onClick={() => void run("accept")} loading={busy}>Accept order</Button>}
        {has("decline") && <Button variant="tertiary" onClick={() => setConfirm("decline")}>Decline</Button>}
        {stageActions.filter((a) => has(a)).map((a) => (
          <Button key={a} variant="secondary" onClick={() => void run(a as Action)} loading={busy}>
            {a === "preparing" ? "Mark preparing" : a === "ready" ? (o.listing_type === "service" ? "Ready to start" : "Ready or out for delivery") : o.listing_type === "service" ? "Mark completed" : "Mark delivered"}
          </Button>
        ))}
        {has("buyer_no_show") && <Button variant="tertiary" onClick={() => setConfirm("buyer_no_show")}>Buyer did not show up</Button>}
        {has("cancel") && <Button variant="tertiary" onClick={() => setConfirm("cancel")}>Cancel order</Button>}
        {o.conversation_id && <Button variant="tertiary" href={`${isBuyer ? "/messages" : "/seller/messages"}/${o.conversation_id}`}>Open chat</Button>}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-lg font-bold">{isBuyer ? "Receipt" : "Order"}</h2>
          {isBuyer ? (
            <BuyerBreakdown o={o} />
          ) : (
            <dl>
              <Row label={`${o.listing_title} × ${o.quantity}`} value={naira(o.unit_price_kobo * o.quantity)} />
              {o.seller_discount_kobo > 0 && <Row label="Your discount" value={`-${naira(o.seller_discount_kobo)}`} />}
              {o.delivery_fee_kobo > 0 && <Row label="Delivery fee" value={naira(o.delivery_fee_kobo)} />}
              <Row label="Buyer pays" value={naira(o.buyer_total_kobo)} />
              {o.commission_kobo != null && <Row label={`Campus Plug commission (${(o.commission_bps ?? 0) / 100}%)`} value={`-${naira(o.commission_kobo)}`} />}
              {o.refunded_item_kobo > 0 && <Row label="Refunded to buyer" value={`-${naira(o.refunded_item_kobo)}`} />}
              <Row label="You receive" value={naira(o.seller_amount_kobo ?? 0)} strong />
              {o.payout_status && <Row label="Payout" value={o.payout_status} />}
            </dl>
          )}
          <p className="mt-3 text-xs text-muted">{isBuyer ? "Seller" : "Buyer"}: {o.other_party}{o.other_phone ? ` · ${o.other_phone}` : ""}</p>
          <p className="text-xs text-muted">{o.fulfilment === "delivery" ? "Delivery to the buyer's hall" : "Pickup"}{o.note ? ` · Note: ${o.note}` : ""}</p>
          <Button variant="tertiary" className="mt-3" onClick={() => window.print()}>
            <Printer className="size-4" aria-hidden="true" /> Print receipt
          </Button>
        </Card>
        <Card>
          <h2 className="mb-2 text-lg font-bold">Progress</h2>
          <Timeline events={o.timeline} />
          {o.accept_by && o.status === "paid" && <p className="mt-3 text-xs text-muted">Seller must accept by {new Date(o.accept_by).toLocaleString("en-NG")}.</p>}
          {o.auto_confirm_at && o.status === "delivered" && <p className="mt-3 text-xs text-muted">Confirms automatically on {new Date(o.auto_confirm_at).toLocaleString("en-NG")} unless you report a problem.</p>}
        </Card>
      </div>

      {o.dispute && (
        <Card className="space-y-3 border-danger-fg" aria-label="Dispute">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-bold">Dispute {o.dispute.public_id}</h2>
            <Badge tone={o.dispute.status === "resolved" ? "verified" : "pending"}>{o.dispute.status.replace("_", " ")}</Badge>
          </div>
          <p className="text-sm"><span className="font-semibold">Reason:</span> {o.dispute.reason.replace(/_/g, " ")}</p>
          <ul className="space-y-2">
            {o.dispute.evidence.map((e, i) => (
              <li key={i} className="rounded-input bg-ground p-3 text-sm">
                <p className="text-xs font-semibold uppercase text-muted">{String(e.by)}</p>
                {e.text ? <p>{String(e.text)}</p> : null}
                {e.image ? <Image src={assetUrl(String(e.image))!} alt={`Evidence from the ${String(e.by)}`} width={240} height={240} unoptimized className="mt-2 h-auto max-h-48 w-auto rounded-input" /> : null}
              </li>
            ))}
          </ul>
          {o.dispute.status === "resolved" && (
            <p className="rounded-input bg-verified-bg p-3 text-sm text-verified-fg">
              Decision: <strong>{o.dispute.resolution.replace("_", " ")}</strong>
              {o.dispute.refund_item_kobo > 0 && ` (${naira(o.dispute.refund_item_kobo)} refunded)`}. {o.dispute.admin_note}
            </p>
          )}
          {!isBuyer && o.role === "seller" && o.dispute.status === "awaiting_seller" && (
            <Button onClick={() => setRespondOpen(true)}>Respond with your side</Button>
          )}
          {o.dispute.status === "awaiting_seller" && o.dispute.response_due_at && <p className="text-xs text-muted">Seller should respond by {new Date(o.dispute.response_due_at).toLocaleString("en-NG")}.</p>}
        </Card>
      )}
      <p className="text-xs text-muted">
        Back to <Link className="underline" href={base === "seller" ? "/seller/orders" : "/orders"}>all orders</Link>
      </p>

      {confirm && !confirmCopy[confirm]?.needsReason && (
        <ConfirmModal open title={confirmCopy[confirm]!.title} body={confirmCopy[confirm]!.body} confirmLabel={confirmCopy[confirm]!.label} destructive={confirmCopy[confirm]!.destructive} loading={busy} onConfirm={() => void run(confirm)} onClose={() => setConfirm(null)} />
      )}
      {confirm && confirmCopy[confirm]?.needsReason && (
        <Modal open title={confirmCopy[confirm]!.title} onClose={() => setConfirm(null)} dirty={reason.length > 0}>
          <p className="mb-3 text-sm text-muted">{confirmCopy[confirm]!.body}</p>
          <Textarea label="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <FormError message={error} />
          <div className="mt-4 flex flex-col-reverse gap-2 md:flex-row md:justify-end">
            <Button variant="tertiary" onClick={() => setConfirm(null)}>Keep order</Button>
            <Button variant="danger" loading={busy} onClick={() => void run(confirm)}>{confirmCopy[confirm]!.label}</Button>
          </div>
        </Modal>
      )}
      <Modal open={respondOpen} title="Respond to the dispute" onClose={() => setRespondOpen(false)} dirty={response.length > 0}>
        <Textarea label="Your side of the story" value={response} onChange={(e) => setResponse(e.target.value)} hint="Be specific. An Admin reads both sides before deciding." />
        <FormError message={error} />
        <Button className="mt-3 w-full" loading={busy} disabled={response.trim().length < 3} onClick={() => void respond()}>Send response</Button>
      </Modal>
    </div>
  );
}
