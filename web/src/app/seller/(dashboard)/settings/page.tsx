"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { FormError } from "@/components/auth/AuthCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { ConfirmModal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/lib/api-schema";

type Settings = components["schemas"]["ShopSettingsOut"];
type Location = components["schemas"]["LocationOut"];

const shopSchema = z.object({ name: z.string().min(2, "Give your shop a name"), bio: z.string().max(600), location_id: z.string() });
const payoutSchema = z.object({
  payout_bank: z.string().min(2, "Enter your bank"),
  payout_account_number: z.string().regex(/^\d{10}$/, "Account numbers have 10 digits"),
  payout_account_name: z.string().min(2, "Enter the account name"),
});

export default function SellerSettings() {
  const client = useQueryClient();
  const toast = useToast();
  const settings = useQuery({ queryKey: ["seller-settings"], queryFn: () => api<Settings>("/seller/settings") });
  const locations = useQuery({ queryKey: ["locations"], queryFn: () => api<Location[]>("/locations") });
  const [holidayConfirm, setHolidayConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const shop = useForm<z.infer<typeof shopSchema>>({ resolver: zodResolver(shopSchema), defaultValues: { name: "", bio: "", location_id: "" } });
  const payout = useForm<z.infer<typeof payoutSchema>>({ resolver: zodResolver(payoutSchema), defaultValues: { payout_bank: "", payout_account_number: "", payout_account_name: "" } });

  useEffect(() => {
    if (!settings.data) return;
    shop.reset({ name: settings.data.name, bio: settings.data.bio, location_id: "" });
    payout.reset({ payout_bank: settings.data.payout_bank ?? "", payout_account_number: "", payout_account_name: settings.data.payout_account_name ?? "" });
  }, [settings.data, shop, payout]);

  async function save(body: Record<string, unknown>, message: string) {
    setError(null);
    try {
      await api("/seller/settings", { method: "PATCH", body });
      await client.invalidateQueries({ queryKey: ["seller-settings"] });
      toast(message);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save.");
    }
  }

  if (settings.isPending) return <div role="status" aria-label="Loading" className="space-y-3"><Skeleton className="h-48" /><Skeleton className="h-48" /></div>;
  if (settings.isError) return <ErrorState message={settings.error.message} onRetry={() => void settings.refetch()} />;
  const s = settings.data;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-extrabold md:text-3xl">Shop settings</h1>
      <Card>
        <h2 className="text-lg font-bold">Shop details</h2>
        <form className="mt-3 space-y-3" noValidate onSubmit={shop.handleSubmit((v) => save({ name: v.name, bio: v.bio, ...(v.location_id ? { location_id: Number(v.location_id) } : {}) }, "Shop updated"))}>
          <Input label="Shop name" error={shop.formState.errors.name?.message} {...shop.register("name")} />
          <Textarea label="About your shop" {...shop.register("bio")} />
          <Select label="Hall or area" hint={s.location_name ? `Currently ${s.location_name}` : undefined} {...shop.register("location_id")}>
            <option value="">Keep current</option>
            {locations.data?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </Select>
          <Button type="submit" variant="secondary" loading={shop.formState.isSubmitting}>Save shop</Button>
        </form>
      </Card>

      <Card>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-bold">Payout details</h2>
          {s.payout_review_required && <Badge tone="pending">Under review</Badge>}
        </div>
        <p className="mt-1 text-sm text-muted">
          {s.payout_account_number_masked ? `Account ${s.payout_account_number_masked} (${s.payout_bank}). ` : ""}
          Changing payout details triggers a review before your next payout.
        </p>
        <form className="mt-3 space-y-3" noValidate onSubmit={payout.handleSubmit((v) => save(v, "Payout details saved"))}>
          <Input label="Bank" error={payout.formState.errors.payout_bank?.message} {...payout.register("payout_bank")} />
          <Input label="Account number" inputMode="numeric" maxLength={10} error={payout.formState.errors.payout_account_number?.message} {...payout.register("payout_account_number")} />
          <Input label="Account name" error={payout.formState.errors.payout_account_name?.message} {...payout.register("payout_account_name")} />
          <FormError message={error} />
          <Button type="submit" variant="secondary" loading={payout.formState.isSubmitting}>Save payout details</Button>
        </form>
      </Card>

      <Card className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">Holiday mode</h2>
          <p className="text-sm text-muted">{s.holiday_mode ? "Your shop is paused and hidden from buyers." : "Pause your shop while you are away."}</p>
        </div>
        <Button variant={s.holiday_mode ? "primary" : "tertiary"} onClick={() => (s.holiday_mode ? void save({ holiday_mode: false }, "Welcome back. Your shop is live.") : setHolidayConfirm(true))}>
          {s.holiday_mode ? "Turn off" : "Turn on"}
        </Button>
      </Card>
      <ConfirmModal open={holidayConfirm} title="Turn on holiday mode?" body="Your listings are hidden from buyers until you turn it off. Open orders are not affected." confirmLabel="Pause my shop" onConfirm={() => { setHolidayConfirm(false); void save({ holiday_mode: true }, "Holiday mode on"); }} onClose={() => setHolidayConfirm(false)} />
    </div>
  );
}
