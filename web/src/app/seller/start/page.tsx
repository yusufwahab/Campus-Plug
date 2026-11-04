"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { AuthCard, FormError } from "@/components/auth/AuthCard";
import { PublicShell } from "@/components/layout/PublicShell";
import { Button } from "@/components/ui/Button";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { RequireAuth, useMe } from "@/lib/auth";

const schema = z.object({
  name: z.string().min(2, "Give your shop a name"),
  bio: z.string().max(600),
  location_id: z.string(),
  accept_rules: z.literal(true, { message: "Accept the seller rules to continue" }),
});
type Values = z.infer<typeof schema>;
type Location = components["schemas"]["LocationOut"];

function StartShop() {
  const me = useMe();
  const router = useRouter();
  const client = useQueryClient();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const locations = useQuery({ queryKey: ["locations"], queryFn: () => api<Location[]>("/locations") });
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { name: "", bio: "", location_id: "" } });
  const errors = form.formState.errors;

  if (me.data?.role === "seller") {
    return (
      <AuthCard title="You already have a shop">
        <Button href="/seller">Go to your dashboard</Button>
      </AuthCard>
    );
  }
  if (me.data && !me.data.phone_verified) {
    return (
      <AuthCard title="Confirm your phone first" subtitle="Sellers must confirm a phone number before opening a shop.">
        <Button href="/verify-phone?next=%2Fseller%2Fstart">Confirm phone number</Button>
      </AuthCard>
    );
  }

  async function onSubmit(v: Values) {
    setError(null);
    try {
      await api("/seller/start", { method: "POST", body: { name: v.name, bio: v.bio, location_id: v.location_id ? Number(v.location_id) : null, accept_rules: true } });
      await client.invalidateQueries({ queryKey: ["me"] });
      toast("Your shop is open");
      router.push("/seller");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not open your shop.");
    }
  }

  return (
    <AuthCard title="Open your shop" subtitle="List in under a minute. Verify later to unlock in-app payments and unlimited listings.">
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <Input label="Shop name" error={errors.name?.message} {...form.register("name")} />
        <Textarea label="About your shop" hint="What do you sell? Where do you deliver?" error={errors.bio?.message} {...form.register("bio")} />
        {locations.isPending ? <Skeleton className="h-11" /> : (
          <Select label="Your hall or area" hint="Never share your room number." {...form.register("location_id")}>
            <option value="">Choose a hall or area</option>
            {locations.data?.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </Select>
        )}
        <div>
          <label className="flex min-h-11 items-start gap-3 text-sm">
            <input type="checkbox" className="mt-0.5 size-5 accent-forest" {...form.register("accept_rules")} />
            <span>
              I have read and accept the{" "}
              <Link href="/seller-rules" target="_blank" className="font-semibold underline">
                seller rules
              </Link>
              .
            </span>
          </label>
          {errors.accept_rules && <p role="alert" className="text-xs font-medium text-danger-fg">{errors.accept_rules.message}</p>}
        </div>
        <FormError message={error} />
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
          Open shop
        </Button>
      </form>
    </AuthCard>
  );
}

export default function SellerStartPage() {
  return (
    <RequireAuth>
      <PublicShell>
        <StartShop />
      </PublicShell>
    </RequireAuth>
  );
}
