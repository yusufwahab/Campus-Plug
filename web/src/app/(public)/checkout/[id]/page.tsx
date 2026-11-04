"use client";
import { useQuery } from "@tanstack/react-query";
import { Lock, WifiOff } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { FormError } from "@/components/auth/AuthCard";
import { BuyerBreakdown, ProtectionBadge, StatusBadge } from "@/components/orders/parts";
import type { Order } from "@/components/orders/parts";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmModal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { ApiError, api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";
import { naira } from "@/lib/format";

function useOnline() {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}

function Checkout() {
  const { id } = useParams<{ id: string }>();
  const online = useOnline();
  const order = useQuery({ queryKey: ["order", id], queryFn: () => api<Order>(`/orders/${id}`) });
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (order.isPending) return <Skeleton className="h-64" />;
  if (order.isError) return <ErrorState message={order.error.message} onRetry={() => void order.refetch()} />;
  const o = order.data;

  async function pay() {
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ checkout_url: string }>(`/orders/${id}/pay`, { method: "POST" });
      window.location.href = res.checkout_url;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start the payment.");
      setBusy(false);
      setConfirm(false);
    }
  }

  const payable = o.status === "pending_payment" && o.role === "buyer";
  return (
    <div className="mx-auto max-w-xl space-y-4 pb-24">
      <h1 className="text-3xl font-extrabold">Checkout</h1>
      <Card className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{o.public_id}</span>
          <StatusBadge status={o.status} />
          <ProtectionBadge order={o} />
        </div>
        <p className="text-sm text-muted">
          From {o.other_party} · {o.fulfilment === "delivery" ? "Delivered to your hall" : "Pickup"}
          {o.booking_at && ` · Booking ${new Date(o.booking_at).toLocaleString("en-NG")}`}
        </p>
        <BuyerBreakdown o={o} />
        {o.deposit_only && <p className="text-xs text-muted">The remaining balance is paid to the seller directly on the day.</p>}
      </Card>
      <Card className="flex items-start gap-3 bg-verified-bg text-verified-fg">
        <Lock className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
        <p className="text-sm">Your payment is held safely. The seller is paid only after you confirm you received your order, or automatically after the confirmation window if you do not raise a problem.</p>
      </Card>
      {!online && (
        <p role="alert" className="flex items-center gap-2 rounded-input bg-danger-bg p-3 text-sm font-semibold text-danger-fg">
          <WifiOff className="size-4" aria-hidden="true" /> You are offline. Payments need a connection.
        </p>
      )}
      <FormError message={error} />
      {payable ? (
        <div className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-30 border-t border-line bg-white p-3 md:static md:border-0 md:bg-transparent md:p-0">
          <Button className="w-full" onClick={() => setConfirm(true)} disabled={!online}>
            Pay {naira(o.buyer_total_kobo)}
          </Button>
        </div>
      ) : (
        <Button href={`/orders/${o.public_id}`}>View this order</Button>
      )}
      <ConfirmModal
        open={confirm}
        title={`Pay ${naira(o.buyer_total_kobo)}?`}
        body="You will go to our secure payment page. The seller only gets paid after you confirm delivery."
        confirmLabel={`Pay ${naira(o.buyer_total_kobo)}`}
        loading={busy}
        onConfirm={() => void pay()}
        onClose={() => setConfirm(false)}
      />
    </div>
  );
}

export default function CheckoutPage() {
  return (
    <RequireAuth>
      <Checkout />
    </RequireAuth>
  );
}
