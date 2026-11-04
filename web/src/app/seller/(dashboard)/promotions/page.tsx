"use client";
import { useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { FormError } from "@/components/auth/AuthCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input, Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { naira, nairaToKobo } from "@/lib/format";
import { useAction, useApiQuery } from "@/lib/hooks";

type Promos = components["schemas"]["SellerPromos"];
type Plans = components["schemas"]["PlansOut"];
type Boost = components["schemas"]["BoostOut"];
type PayStart = components["schemas"]["PayStart"];
type Listing = { public_id: string; title: string; status: string };

const BOOST_PRICE: Record<string, number> = { "3": 150_000, "7": 350_000, "14": 700_000 };

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h2 id={id} className="text-xl font-bold">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Content() {
  const params = useSearchParams();
  const client = useQueryClient();
  const toast = useToast();
  const promos = useApiQuery<Promos>(["seller-promos"], "/seller/promos");
  const plans = useApiQuery<Plans>(["seller-plans"], "/plans");
  const boosts = useApiQuery<Boost[]>(["seller-boosts"], "/seller/boosts");
  const listings = useApiQuery<Listing[]>(["seller-listings-all"], "/seller/listings");
  const act = useAction([["seller-promos"], ["seller-plans"], ["seller-boosts"]]);
  const [form, setForm] = useState({ code: "", kind: "percent", amount: "", min: "", limit: "" });
  const [adminCode, setAdminCode] = useState("");
  const [boostForm, setBoostForm] = useState({ listing: "", days: "3" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Coming back from checkout: confirm the payment, then refresh everything.
  const reference = params.get("reference") ?? params.get("trxref");
  useEffect(() => {
    if (!reference) return;
    void api<{ status: string }>(`/seller/purchases/${reference}/status`)
      .then((r) => {
        toast(r.status === "applied" || r.status === "paid" ? "Payment confirmed" : "Payment is still processing");
        for (const key of ["seller-plans", "seller-boosts"]) void client.invalidateQueries({ queryKey: [key] });
      })
      .catch(() => undefined);
  }, [reference, client, toast]);

  async function pay(path: string, body: unknown) {
    setBusy(true);
    setError(null);
    try {
      const started = await api<PayStart>(path, { method: "POST", body });
      window.location.assign(started.checkout_url);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start the payment.");
      setBusy(false);
    }
  }

  async function createCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const amount = Number(form.amount);
    if (!form.code || !amount || amount <= 0) {
      setError("Enter a code and a discount amount.");
      return;
    }
    const body = {
      code: form.code,
      ...(form.kind === "percent" ? { percent: amount } : { fixed_kobo: nairaToKobo(amount) }),
      min_spend_kobo: form.min ? nairaToKobo(Number(form.min)) : 0,
      usage_limit: form.limit ? Number(form.limit) : null,
    };
    try {
      await act("POST", "/seller/promos", body, "Code created");
      setForm({ code: "", kind: "percent", amount: "", min: "", limit: "" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the code.");
    }
  }

  const live = (listings.data ?? []).filter((l) => l.status === "active");
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-extrabold md:text-3xl">Promotions</h1>
      <p className="max-w-prose text-sm text-muted">
        Discount codes you create come out of your price, so commission is charged on what the buyer actually pays. Plans and boosts are paid to Campus Plug.
      </p>
      {error && <FormError message={error} />}

      <Section id="plans" title="Premium plan">
        {plans.isPending ? (
          <Skeleton className="h-32" />
        ) : plans.isError ? (
          <ErrorState message={plans.error.message} onRetry={() => void plans.refetch()} />
        ) : plans.data.plans.length === 0 ? (
          <EmptyState title="No plans yet" body="Premium plans will appear here when Campus Plug publishes them." />
        ) : (
          <>
            {plans.data.current_plan && (
              <p className="rounded-card bg-verified-bg p-4 text-sm text-verified-fg">
                You are on <strong>{plans.data.current_plan}</strong> until {new Date(plans.data.current_ends_at ?? "").toLocaleDateString("en-NG")}.{" "}
                <button className="font-semibold underline" onClick={() => void act("POST", "/seller/plan/cancel", undefined, "Plan cancelled")}>
                  Cancel plan
                </button>
              </p>
            )}
            <ul className="grid gap-3 md:grid-cols-2">
              {plans.data.plans.map((p) => (
                <li key={p.id}>
                  <Card className="space-y-2">
                    <h3 className="text-lg font-bold">{p.name}</h3>
                    <p className="font-heading text-2xl font-extrabold">
                      {naira(p.price_kobo)} <span className="text-sm font-normal text-muted">for {p.period_days} days</span>
                    </p>
                    {p.commission_bps !== null && p.commission_bps !== undefined && <p className="text-sm">Commission {p.commission_bps / 100}% on new orders</p>}
                    <ul className="list-disc pl-5 text-sm text-muted">{p.benefits.map((b) => <li key={b}>{b}</li>)}</ul>
                    <Button loading={busy} onClick={() => void pay("/seller/plan/buy", { plan_id: p.id })}>
                      {plans.data.current_plan === p.name ? "Renew" : "Buy plan"}
                    </Button>
                  </Card>
                </li>
              ))}
            </ul>
          </>
        )}
      </Section>

      <Section id="boosts" title="Boost a listing">
        <Card className="space-y-3">
          <p className="text-sm text-muted">A boosted listing is shown first in search and marked Sponsored, after Campus Plug approves it. A rejected boost is refunded.</p>
          <div className="grid gap-3 md:grid-cols-3">
            <Select label="Listing" value={boostForm.listing} onChange={(e) => setBoostForm({ ...boostForm, listing: e.target.value })}>
              <option value="">Choose a listing</option>
              {live.map((l) => (
                <option key={l.public_id} value={l.public_id}>
                  {l.title}
                </option>
              ))}
            </Select>
            <Select label="Length" value={boostForm.days} onChange={(e) => setBoostForm({ ...boostForm, days: e.target.value })}>
              {Object.entries(BOOST_PRICE).map(([d, p]) => (
                <option key={d} value={d}>
                  {d} days, {naira(p)}
                </option>
              ))}
            </Select>
            <div className="flex items-end">
              <Button loading={busy} disabled={!boostForm.listing} onClick={() => void pay("/seller/boosts", { listing_id: boostForm.listing, days: Number(boostForm.days) })}>
                Pay for boost
              </Button>
            </div>
          </div>
        </Card>
        {(boosts.data ?? []).length > 0 && (
          <ul aria-label="Your boosts" className="space-y-2">
            {boosts.data?.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center justify-between gap-2 rounded-card border border-line bg-white p-3 text-sm">
                <span>
                  {b.listing_id}, {b.days} days, {naira(b.price_kobo)}
                </span>
                <Badge tone={b.status === "active" ? "verified" : b.status === "pending" ? "pending" : "neutral"}>{b.status === "pending" ? "Waiting for approval" : b.status}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section id="codes" title="Your discount codes">
        <form onSubmit={createCode} noValidate className="grid gap-3 rounded-card border border-line bg-white p-4 md:grid-cols-3">
          <Input label="Code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} hint="3 to 20 letters or numbers" />
          <Select label="Type" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            <option value="percent">Percentage off</option>
            <option value="fixed">Fixed amount off (₦)</option>
          </Select>
          <Input label={form.kind === "percent" ? "Percent" : "Amount (₦)"} inputMode="numeric" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          <Input label="Minimum spend (₦)" inputMode="numeric" value={form.min} onChange={(e) => setForm({ ...form, min: e.target.value })} hint="Optional" />
          <Input label="Uses allowed" inputMode="numeric" value={form.limit} onChange={(e) => setForm({ ...form, limit: e.target.value })} hint="Optional" />
          <div className="flex items-end">
            <Button type="submit">Create code</Button>
          </div>
        </form>
        {promos.isPending ? (
          <Skeleton className="h-20" />
        ) : promos.isError ? (
          <ErrorState message={promos.error.message} onRetry={() => void promos.refetch()} />
        ) : promos.data.codes.length === 0 ? (
          <EmptyState title="No codes yet" body="Create a code above and share it in chats or on social media." />
        ) : (
          <ul aria-label="Your codes" className="space-y-2">
            {promos.data.codes.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-card border border-line bg-white p-3 text-sm">
                <span>
                  <strong>{c.code}</strong>, {c.percent ? `${c.percent}% off` : `${naira(c.fixed_kobo ?? 0)} off`}, used {c.used}
                  {c.usage_limit ? ` of ${c.usage_limit}` : ""}
                </span>
                <Button variant="tertiary" onClick={() => void act("POST", `/seller/promos/${c.id}/active`, undefined, c.active ? "Code turned off" : "Code turned on", { active: !c.active })}>
                  {c.active ? "Turn off" : "Turn on"}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section id="admin-code" title="Have a code from Campus Plug?">
        <form
          noValidate
          className="flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void act("POST", "/seller/promos/apply", { code: adminCode }, "Code applied to new orders")
              .then(() => setAdminCode(""))
              .catch((err) => setError(err instanceof ApiError ? err.message : "Could not apply the code."));
          }}
        >
          <Input label="Commission code" value={adminCode} onChange={(e) => setAdminCode(e.target.value)} />
          <Button type="submit" disabled={adminCode.trim().length < 2}>
            Apply code
          </Button>
        </form>
        {promos.data?.applied_admin_codes.map((a) => (
          <p key={a.code} className="text-sm text-muted">
            {a.code} applied: {a.commission_bps !== null && a.commission_bps !== undefined ? `${a.commission_bps / 100}% commission on new orders` : "active"}
          </p>
        ))}
      </Section>
    </div>
  );
}

export default function SellerPromotions() {
  return (
    <Suspense fallback={<Skeleton className="h-64" />}>
      <Content />
    </Suspense>
  );
}
