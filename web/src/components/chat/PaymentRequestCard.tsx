"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { naira } from "@/lib/format";

type Message = components["schemas"]["MessageOut"];

type Payload = { title?: string; agreed_price_kobo: number; quantity: number; delivery_fee_kobo: number; note?: string; status: string; order_id?: string };

/** Structured payment request the seller sends in chat. The buyer opens checkout from it. */
export function PaymentRequestCard({ message }: { message: Message }) {
  const p = message.payload as unknown as Payload;
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const total = p.agreed_price_kobo * p.quantity + p.delivery_fee_kobo;

  async function open() {
    setBusy(true);
    try {
      const order = await api<{ public_id: string }>("/orders", { method: "POST", body: { message_id: message.id } });
      router.push(`/checkout/${order.public_id}`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not open checkout", "error");
      setBusy(false);
    }
  }

  return (
    <div className="min-w-56 space-y-1" data-testid="payment-request">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">Payment request</p>
      <p className="font-heading text-xl font-extrabold">{naira(total)}</p>
      <p className="text-sm">
        {p.quantity} × {p.title ?? "item"} at {naira(p.agreed_price_kobo)}
        {p.delivery_fee_kobo > 0 && ` + ${naira(p.delivery_fee_kobo)} delivery`}
      </p>
      {p.note && <p className="text-sm text-muted">{p.note}</p>}
      {p.status === "pending" && !message.mine && (
        <Button className="mt-2 w-full" onClick={() => void open()} loading={busy}>
          Pay {naira(total)}
        </Button>
      )}
      {p.status === "pending" && message.mine && <p className="text-xs text-muted">Waiting for the buyer to pay</p>}
      {p.status !== "pending" && p.order_id && (
        <Link href={message.mine ? `/seller/orders/${p.order_id}` : `/orders/${p.order_id}`} className="mt-1 inline-flex min-h-11 items-center text-sm font-semibold underline">
          {p.status === "paid" ? "Paid" : "Order started"}: {p.order_id}
        </Link>
      )}
    </div>
  );
}
