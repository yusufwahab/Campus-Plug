"use client";
import { ShoppingBag } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { FormError } from "@/components/auth/AuthCard";
import { SignInPrompt } from "@/components/auth/SignInPrompt";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { ApiError, api } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { naira } from "@/lib/format";

type Props = {
  listingId: string;
  type: string;
  priceKobo: number;
  depositKobo: number | null | undefined;
  fulfilment: string;
  deliveryFeeKobo: number;
  quantityAvailable: number;
  preorder: boolean;
  sellerVerified: boolean;
  className?: string;
};

/** Buy (products) or Book (services). Starts with the delivery choice, then goes to checkout. */
export function BuyButton(p: Props) {
  const me = useMe();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState(false);
  const [fulfilment, setFulfilment] = useState<"pickup" | "delivery">(p.fulfilment === "delivery" ? "delivery" : "pickup");
  const [quantity, setQuantity] = useState("1");
  const [booking, setBooking] = useState("");
  const [note, setNote] = useState("");
  const [promo, setPromo] = useState("");
  const [promoMsg, setPromoMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [discount, setDiscount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isService = p.type === "service";
  const verb = isService ? "Book" : "Buy";

  const qty = Math.max(1, Number(quantity) || 1);
  const unit = isService && p.depositKobo ? p.depositKobo : p.priceKobo;
  const delivery = fulfilment === "delivery" ? p.deliveryFeeKobo : 0;
  const total = Math.max(unit * (isService && p.depositKobo ? 1 : qty) + delivery - discount, 0);

  async function checkPromo() {
    setPromoMsg(null);
    setDiscount(0);
    if (!promo.trim()) return;
    try {
      const r = await api<{ discount_kobo: number; description: string }>("/promos/validate", { method: "POST", body: { code: promo.trim(), listing_id: p.listingId, quantity: qty } });
      setDiscount(r.discount_kobo);
      setPromoMsg({ ok: true, text: `${r.description}: ${naira(r.discount_kobo)} off` });
    } catch (err) {
      setPromoMsg({ ok: false, text: err instanceof ApiError ? err.message : "Could not check the code." });
    }
  }

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (isService && !booking) return setError("Choose a date and time for your booking.");
    setBusy(true);
    try {
      const order = await api<{ public_id: string }>("/orders", {
        method: "POST",
        body: { listing_id: p.listingId, quantity: qty, fulfilment, booking_at: booking ? new Date(booking).toISOString() : null, note, promo_code: promo.trim() || null },
      });
      router.push(`/checkout/${order.public_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start your order.");
      setBusy(false);
    }
  }

  if (!p.sellerVerified) {
    return (
      <p className="rounded-input bg-pending-bg p-3 text-sm text-pending-fg">
        This seller is not verified yet, so in-app payment is off. Message them to agree a cash deal. Cash deals are marked Not protected.
      </p>
    );
  }
  return (
    <>
      <Button className={p.className} onClick={() => (me.data ? setOpen(true) : setPrompt(true))} disabled={me.isPending}>
        <ShoppingBag className="size-4" aria-hidden="true" />
        {verb} now
      </Button>
      <SignInPrompt open={prompt} onClose={() => setPrompt(false)} reason={isService ? "book this service" : "buy this item"} />
      <Modal open={open} title={isService ? "Book this service" : "Choose how you get it"} onClose={() => setOpen(false)} dirty={note.length > 0}>
        <form onSubmit={start} className="space-y-4" noValidate>
          {!isService ? (
            <fieldset>
              <legend className="text-sm font-semibold">Collection</legend>
              <div className="mt-2 grid gap-2">
                {(["pickup", "delivery"] as const)
                  .filter((f) => p.fulfilment === "both" || p.fulfilment === f)
                  .map((f) => (
                    <label key={f} className={`flex min-h-11 cursor-pointer items-center justify-between rounded-input border-2 px-4 text-sm font-semibold ${fulfilment === f ? "border-ink bg-lime/30" : "border-line"}`}>
                      <span className="flex items-center gap-2">
                        <input type="radio" name="fulfilment" value={f} checked={fulfilment === f} onChange={() => setFulfilment(f)} className="accent-forest" />
                        {f === "pickup" ? "Pick up from the seller" : "Seller delivers to my hall"}
                      </span>
                      <span className="text-muted">{f === "delivery" ? (p.deliveryFeeKobo ? naira(p.deliveryFeeKobo) : "Free") : "Free"}</span>
                    </label>
                  ))}
              </div>
            </fieldset>
          ) : null}
          {!isService && <Input label="Quantity" inputMode="numeric" value={quantity} onChange={(e) => setQuantity(e.target.value.replace(/\D/g, ""))} hint={p.preorder ? "Pre-order: the seller prepares it for you." : `${p.quantityAvailable} available`} />}
          {isService && <Input label="Date and time" type="datetime-local" value={booking} onChange={(e) => setBooking(e.target.value)} hint={p.depositKobo ? `You pay a ${naira(p.depositKobo)} deposit now. The rest is paid to the seller directly.` : undefined} />}
          <Textarea label="Note to the seller (optional)" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="space-y-1.5">
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Input label="Promo code (optional)" value={promo} onChange={(e) => { setPromo(e.target.value); setDiscount(0); setPromoMsg(null); }} autoCapitalize="characters" />
              </div>
              <Button variant="secondary" onClick={() => void checkPromo()} disabled={!promo.trim()}>Apply</Button>
            </div>
            {promoMsg && <p role="status" className={`text-xs font-medium ${promoMsg.ok ? "text-verified-fg" : "text-danger-fg"}`}>{promoMsg.text}</p>}
          </div>
          <p className="rounded-input bg-ground p-3 text-sm">
            {p.depositKobo && isService ? "Deposit" : "Total"}: <strong>{naira(total)}</strong>
          </p>
          <FormError message={error} />
          <Button type="submit" className="w-full" loading={busy}>Continue to checkout</Button>
        </form>
      </Modal>
    </>
  );
}
