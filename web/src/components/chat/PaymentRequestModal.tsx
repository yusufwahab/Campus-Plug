"use client";
import { useState } from "react";
import { FormError } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import { naira, nairaToKobo } from "@/lib/format";

/** Seller sends the agreed price as a structured payment request. */
export function PaymentRequestModal({ open, conversationId, defaultPriceKobo, onClose, onSent }: { open: boolean; conversationId: number; defaultPriceKobo: number; onClose: () => void; onSent: () => Promise<void> }) {
  const toast = useToast();
  const [price, setPrice] = useState(defaultPriceKobo ? String(defaultPriceKobo / 100) : "");
  const [quantity, setQuantity] = useState("1");
  const [delivery, setDelivery] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const valid = /^\d+(\.\d{1,2})?$/.test(price) && Number(price) > 0 && /^\d+$/.test(quantity) && Number(quantity) > 0 && (delivery === "" || /^\d+(\.\d{1,2})?$/.test(delivery));
  const total = valid ? nairaToKobo(Number(price)) * Number(quantity) + (delivery ? nairaToKobo(Number(delivery)) : 0) : 0;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return setError("Enter the agreed price and quantity as numbers.");
    setBusy(true);
    setError(null);
    try {
      await api(`/conversations/${conversationId}/payment-request`, {
        method: "POST",
        body: { agreed_price_kobo: nairaToKobo(Number(price)), quantity: Number(quantity), delivery_fee_kobo: delivery ? nairaToKobo(Number(delivery)) : 0, note },
      });
      await onSent();
      toast("Payment request sent");
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send the request.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} title="Request a payment" onClose={onClose} dirty={note.length > 0}>
      <form onSubmit={submit} className="space-y-3" noValidate>
        <p className="text-sm text-muted">Send the agreed price. The buyer pays inside the app and your money is held until they confirm delivery.</p>
        <Input label="Agreed price per item (₦)" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
        <Input label="Quantity" inputMode="numeric" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        <Input label="Delivery fee (₦, optional)" inputMode="decimal" value={delivery} onChange={(e) => setDelivery(e.target.value)} />
        <Textarea label="Note (optional)" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        <p className="rounded-input bg-ground p-3 text-sm">Buyer will pay <strong>{naira(total)}</strong></p>
        <FormError message={error} />
        <Button type="submit" className="w-full" loading={busy}>Send payment request</Button>
      </form>
    </Modal>
  );
}
