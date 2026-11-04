"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthCard, FormError } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { ApiError, api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";
import { safeNext } from "@/lib/safe-next";

type Campus = { id: number; name: string };
type Location = { id: number; name: string; campus_id: number };
type Category = { id: number; slug: string; name: string; tint: string };

const tintClass: Record<string, string> = { peach: "bg-peach", lilac: "bg-lilac", sky: "bg-sky", butter: "bg-butter", mint: "bg-mint" };

function Onboarding() {
  const router = useRouter();
  const client = useQueryClient();
  const next = safeNext(useSearchParams().get("next"));
  const campuses = useQuery({ queryKey: ["campuses"], queryFn: () => api<Campus[]>("/campuses") });
  const locations = useQuery({ queryKey: ["locations"], queryFn: () => api<Location[]>("/locations") });
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/categories") });
  const [campusId, setCampusId] = useState<number | null>(null);
  const [locationId, setLocationId] = useState<number | null>(null);
  const [interests, setInterests] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const failed = campuses.isError || locations.isError || categories.isError;
  const loading = campuses.isPending || locations.isPending || categories.isPending;
  const campus = campusId ?? campuses.data?.[0]?.id ?? null;

  async function save() {
    if (!campus) return;
    setSaving(true);
    setError(null);
    try {
      await api("/me/onboarding", { method: "POST", body: { campus_id: campus, location_id: locationId, interests } });
      await client.invalidateQueries({ queryKey: ["me"] });
      router.push(next);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save your choices.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AuthCard title="Set up your campus" subtitle="We use this to show sellers near you. You can change it any time.">
      {failed && <ErrorState message="Could not load campuses." onRetry={() => { void campuses.refetch(); void locations.refetch(); void categories.refetch(); }} />}
      {loading && !failed && (
        <div role="status" aria-label="Loading" className="space-y-3">
          <Skeleton className="h-11" />
          <Skeleton className="h-11" />
          <Skeleton className="h-24" />
        </div>
      )}
      {campuses.data && locations.data && categories.data && (
        <div className="space-y-5">
          <Select label="Campus" value={campus ?? ""} onChange={(e) => { setCampusId(Number(e.target.value)); setLocationId(null); }}>
            {campuses.data.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <Select label="Where are you?" value={locationId ?? ""} onChange={(e) => setLocationId(e.target.value ? Number(e.target.value) : null)} hint="A hall or general area. Never share your room number.">
            <option value="">Choose a hall or area</option>
            {locations.data
              .filter((l) => l.campus_id === campus)
              .map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
          </Select>
          <fieldset>
            <legend className="text-sm font-semibold">What are you into?</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {categories.data.map((c) => {
                const on = interests.includes(c.slug);
                return (
                  <button
                    key={c.slug}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setInterests(on ? interests.filter((s) => s !== c.slug) : [...interests, c.slug])}
                    className={clsx("min-h-11 rounded-full border-2 px-4 text-sm font-semibold", on ? "border-ink " + (tintClass[c.tint] ?? "bg-mint") : "border-line bg-white")}
                  >
                    {c.name}
                  </button>
                );
              })}
            </div>
          </fieldset>
          <FormError message={error} />
          <Button className="w-full" onClick={save} loading={saving}>
            Finish
          </Button>
        </div>
      )}
    </AuthCard>
  );
}

export default function OnboardingPage() {
  return (
    <RequireAuth>
      <Suspense>
        <Onboarding />
      </Suspense>
    </RequireAuth>
  );
}
