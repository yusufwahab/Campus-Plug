"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { FormError } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Select, Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { RequireAuth } from "@/lib/auth";
import { nairaToKobo } from "@/lib/format";

const schema = z.object({
  title: z.string().min(3, "Say what you need"),
  description: z.string().max(1500),
  category_id: z.string(),
  budget: z.string().refine((v) => v === "" || /^\d+(\.\d{1,2})?$/.test(v), "Enter an amount in naira"),
  location_id: z.string(),
  deadline: z.string(),
});
type Values = z.infer<typeof schema>;

function NewRequest() {
  const router = useRouter();
  const client = useQueryClient();
  const toast = useToast();
  const q = useSearchParams().get("q") ?? "";
  const [error, setError] = useState<string | null>(null);
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<components["schemas"]["CategoryOut"][]>("/categories") });
  const locations = useQuery({ queryKey: ["locations"], queryFn: () => api<components["schemas"]["LocationOut"][]>("/locations") });
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { title: q, description: "", category_id: "", budget: "", location_id: "", deadline: "" } });
  const errors = form.formState.errors;

  async function onSubmit(v: Values) {
    setError(null);
    try {
      const res = await api<{ id: number }>("/requests", {
        method: "POST",
        body: {
          title: v.title,
          description: v.description,
          category_id: v.category_id ? Number(v.category_id) : null,
          budget_kobo: v.budget ? nairaToKobo(Number(v.budget)) : null,
          location_id: v.location_id ? Number(v.location_id) : null,
          deadline: v.deadline ? new Date(v.deadline).toISOString() : null,
        },
      });
      await client.invalidateQueries({ queryKey: ["requests"] });
      toast("Request posted. Matching sellers have been told.");
      router.push(`/requests/${res.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not post your request.");
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-3xl font-extrabold">Plug Me</h1>
      <p className="text-sm text-muted">Tell the campus what you need. Sellers who can help will message you.</p>
      <Card>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <Input label="What do you need?" error={errors.title?.message} {...form.register("title")} />
          <Textarea label="Details" hint="Size, colour, brand, when you need it. Do not include room numbers." {...form.register("description")} />
          <Select label="Category" {...form.register("category_id")}>
            <option value="">Not sure</option>
            {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
          <Input label="Budget (₦, optional)" inputMode="decimal" error={errors.budget?.message} {...form.register("budget")} />
          <Select label="Your hall or area" {...form.register("location_id")}>
            <option value="">Anywhere on campus</option>
            {locations.data?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </Select>
          <Input label="Needed by (optional)" type="datetime-local" {...form.register("deadline")} />
          <FormError message={error} />
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>Post request</Button>
        </form>
      </Card>
    </div>
  );
}

export default function NewRequestPage() {
  return (
    <RequireAuth>
      <Suspense>
        <NewRequest />
      </Suspense>
    </RequireAuth>
  );
}
