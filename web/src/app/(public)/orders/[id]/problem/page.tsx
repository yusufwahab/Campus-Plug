"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { FormError } from "@/components/auth/AuthCard";
import type { Order } from "@/components/orders/parts";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, Textarea } from "@/components/ui/Field";
import { ConfirmModal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";
import { compressImage } from "@/lib/image";

const schema = z.object({
  reason: z.enum(["not_received", "not_as_described", "damaged", "wrong_item", "no_show", "other"]),
  details: z.string().min(10, "Tell us what went wrong (at least 10 characters)").max(2000),
});
type Values = z.infer<typeof schema>;

function Problem() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const client = useQueryClient();
  const toast = useToast();
  const order = useQuery({ queryKey: ["order", id], queryFn: () => api<Order>(`/orders/${id}`) });
  const [photo, setPhoto] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Values | null>(null);
  const [busy, setBusy] = useState(false);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { reason: "not_as_described", details: "" } });

  if (order.isPending) return <Skeleton className="h-64" />;
  if (order.isError) return <ErrorState message={order.error.message} onRetry={() => void order.refetch()} />;
  const o = order.data;
  if (!o.actions.includes("problem")) {
    return (
      <Card className="mx-auto max-w-xl space-y-3">
        <h1 className="text-2xl font-extrabold">You cannot report a problem on this order</h1>
        <p className="text-sm text-muted">{o.dispute ? "A dispute is already open for this order." : "Problems can be reported on protected orders that are accepted, in progress or delivered."}</p>
        <Button href={`/orders/${o.public_id}`}>Back to the order</Button>
      </Card>
    );
  }

  async function submit(v: Values) {
    setBusy(true);
    setError(null);
    try {
      const updated = await api<Order>(`/orders/${id}/problem`, { method: "POST", body: v });
      if (photo && updated.dispute) {
        const data = new FormData();
        data.append("file", await compressImage(photo));
        data.append("note", "Photo evidence");
        await api(`/disputes/${updated.dispute.public_id}/evidence`, { method: "POST", body: data });
      }
      await client.invalidateQueries({ queryKey: ["order", id] });
      await client.invalidateQueries({ queryKey: ["orders"] });
      toast("Problem reported. The seller's payout is paused.");
      router.push(`/orders/${id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not report the problem.");
      setPending(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-3xl font-extrabold">Report a problem</h1>
      <p className="text-sm text-muted">Order {o.public_id}. The seller&apos;s payout is paused while we look into it. The seller responds, then an Admin decides.</p>
      <Card>
        <form onSubmit={form.handleSubmit((v) => setPending(v))} className="space-y-4" noValidate>
          <Select label="What went wrong?" {...form.register("reason")}>
            <option value="not_received">I did not receive it</option>
            <option value="not_as_described">Not as described</option>
            <option value="damaged">It arrived damaged</option>
            <option value="wrong_item">Wrong item</option>
            <option value="no_show">Seller did not show up</option>
            <option value="other">Something else</option>
          </Select>
          <Textarea label="What happened?" error={form.formState.errors.details?.message} {...form.register("details")} />
          <div>
            <label htmlFor="evidence" className="text-sm font-semibold">Photo (optional)</label>
            <input id="evidence" type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} className="mt-1 block w-full min-h-11 rounded-input border border-line bg-white p-2 text-sm" />
          </div>
          <FormError message={error} />
          <Button type="submit" variant="danger" className="w-full">Report problem</Button>
        </form>
      </Card>
      <ConfirmModal open={!!pending} title="Report this problem?" body="Your payment stays held while the dispute is open. Only report real problems." confirmLabel="Report problem" destructive loading={busy} onConfirm={() => pending && void submit(pending)} onClose={() => setPending(null)} />
    </div>
  );
}

export default function ProblemPage() {
  return (
    <RequireAuth>
      <Problem />
    </RequireAuth>
  );
}
