"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { FormError } from "@/components/auth/AuthCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ApiError, api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";

/**
 * TEST CHECKOUT. Used only while PAYMENT_PROVIDER=local (no payment account connected yet).
 * No real money moves. With Paystack configured, buyers are sent to Paystack's own page instead.
 */
function LocalCheckout() {
  const reference = useSearchParams().get("reference") ?? "";
  const router = useRouter();
  const [busy, setBusy] = useState<"success" | "failed" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function complete(outcome: "success" | "failed") {
    setBusy(outcome);
    setError(null);
    try {
      const res = await api<{ order: string }>("/payments/local/complete", { method: "POST", body: { reference, outcome } });
      const ref = encodeURIComponent(reference);
      // Plan and boost purchases have no order; they return to the seller Promotions page.
      router.push(res.order ? `/checkout/${res.order}/result?reference=${ref}` : `/seller/promotions?purchase=done&reference=${ref}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not complete the test payment.");
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-4 py-8">
      <Card className="space-y-3">
        <Badge tone="pending">Test mode: no real money</Badge>
        <h1 className="text-2xl font-extrabold">Test payment page</h1>
        <p className="text-sm text-muted">This stands in for the payment provider until a real account is connected. Choose the outcome to simulate.</p>
        <p className="break-all text-xs text-muted">Reference: {reference}</p>
        <FormError message={error} />
        <div className="flex flex-col gap-2">
          <Button onClick={() => void complete("success")} loading={busy === "success"} disabled={!reference}>
            Simulate successful payment
          </Button>
          <Button variant="tertiary" onClick={() => void complete("failed")} loading={busy === "failed"} disabled={!reference}>
            Simulate failed payment
          </Button>
        </div>
      </Card>
    </div>
  );
}

export default function LocalCheckoutPage() {
  return (
    <RequireAuth>
      <Suspense>
        <LocalCheckout />
      </Suspense>
    </RequireAuth>
  );
}
