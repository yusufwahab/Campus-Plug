"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { FormError } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import { nairaToKobo } from "@/lib/format";

/** Records a cash or direct transfer deal. Both people must confirm it. It is Not protected. */
export function OfflineDealModal({ open, conversationId, defaultPriceKobo, iAmSeller, onClose }: { open: boolean; conversationId: number; defaultPriceKobo: number; iAmSeller: boolean; onClose: () => void }) {
  const router = useRouter();
  const toast = useToast();
  const [price, setPrice] = useState(defaultPriceKobo ? String(defaultPriceKobo / 100) : "");
  const [quantity, setQuantity] = useState("1");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!/^\d+(\.\d{1,2})?$/.test(price) || Number(price) <= 0) return setError("Enter the agreed price in naira.");
    setBusy(true);
    setError(null);
    try {
      const order = await api<{ public_id: string }>("/orders/offline", { method: "POST", body: { conversation_id: conversationId, agreed_price_kobo: nairaToKobo(Number(price)), quantity: Number(quantity) || 1 } });
      toast("Cash deal recorded. The other person must confirm it too.");
      router.push(iAmSeller ? `/seller/orders/${order.public_id}` : `/orders/${order.public_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record the deal.");
      setBusy(false);
    }
  }

  return (
    <Modal open={open} title="Record a cash deal" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3" noValidate>
        <p className="rounded-input bg-pending-bg p-3 text-sm text-pending-fg">Cash and direct transfers are Not protected. Campus Plug cannot refund them or settle disputes. Pay in the app for protection.</p>
        <Input label="Agreed price (₦)" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
        <Input label="Quantity" inputMode="numeric" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        <FormError message={error} />
        <Button type="submit" className="w-full" loading={busy}>Record deal</Button>
      </form>
    </Modal>
  );
}
