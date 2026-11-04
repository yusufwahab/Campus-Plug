"use client";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { BuyerBreakdown } from "@/components/orders/parts";
import type { Order } from "@/components/orders/parts";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";

function Result() {
  const { id } = useParams<{ id: string }>();
  const reference = useSearchParams().get("reference");
  const [tries, setTries] = useState(0);
  const order = useQuery({
    queryKey: ["order-result", id, reference],
    queryFn: () => {
      setTries((n) => n + 1);
      return api<Order>(`/orders/${id}/payment-status`, { query: { reference } });
    },
    // Keep checking for a short while: the provider can take a moment to confirm.
    refetchInterval: (q) => (q.state.data?.status === "pending_payment" && q.state.dataUpdateCount < 6 ? 2500 : false),
  });

  if (order.isPending) return <Skeleton className="h-64" />;
  if (order.isError) return <ErrorState message={order.error.message} onRetry={() => void order.refetch()} />;
  const o = order.data;
  const failed = o.status === "pending_payment";
  const checking = failed && tries < 6;

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <Card className="space-y-3 text-center">
        {checking ? (
          <>
            <p role="status" className="font-heading text-2xl font-extrabold">Confirming your payment…</p>
            <p className="text-sm text-muted">This usually takes a few seconds. Please do not pay again.</p>
          </>
        ) : failed ? (
          <>
            <XCircle className="mx-auto size-12 text-danger-fg" aria-hidden="true" />
            <h1 className="text-2xl font-extrabold">Payment not completed</h1>
            <p className="text-sm text-muted">You have not been charged for this order. You can try again.</p>
            <Button href={`/checkout/${o.public_id}`}>Try payment again</Button>
          </>
        ) : o.status === "cancelled" ? (
          <>
            <XCircle className="mx-auto size-12 text-danger-fg" aria-hidden="true" />
            <h1 className="text-2xl font-extrabold">This order was cancelled</h1>
            <p className="text-sm text-muted">{o.cancel_reason}</p>
          </>
        ) : (
          <>
            <CheckCircle2 className="mx-auto size-12 text-forest" aria-hidden="true" />
            <h1 className="text-2xl font-extrabold">Payment received</h1>
            <p className="text-sm text-muted">Your money is held safely until you confirm delivery. The seller has been told.</p>
          </>
        )}
      </Card>
      {!failed && (
        <Card className="space-y-2" aria-label="Receipt">
          <h2 className="text-lg font-bold">Receipt</h2>
          <p className="text-sm text-muted">Order ID <strong className="text-ink">{o.public_id}</strong> · {o.paid_at ? new Date(o.paid_at).toLocaleString("en-NG") : ""}</p>
          <BuyerBreakdown o={o} />
          <div className="flex flex-wrap gap-2 pt-2">
            <Button href={`/orders/${o.public_id}`}>Track this order</Button>
            {o.conversation_id && <Button href={`/messages/${o.conversation_id}`} variant="tertiary">Message seller</Button>}
          </div>
        </Card>
      )}
    </div>
  );
}

export default function ResultPage() {
  return (
    <RequireAuth>
      <Suspense>
        <Result />
      </Suspense>
    </RequireAuth>
  );
}
