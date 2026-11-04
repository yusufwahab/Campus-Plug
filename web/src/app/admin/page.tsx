"use client";
import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/admin/PageHeader";
import { Select } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { API_ORIGIN, tokenStore } from "@/lib/api";
import { naira } from "@/lib/format";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import type { components } from "@/lib/api-schema";
import { useApiQuery } from "@/lib/hooks";

type Overview = components["schemas"]["Overview"];
type Analytics = components["schemas"]["AdminAnalytics"];

function AnalyticsPanel() {
  const [days, setDays] = useState("30");
  const toast = useToast();
  async function downloadAnalytics() {
    try {
      const res = await fetch(`${API_ORIGIN}/api/v1/admin/analytics.csv?days=${days}`, { headers: { Authorization: `Bearer ${tokenStore.get()}` } });
      if (!res.ok) throw new Error("failed");
      const url = URL.createObjectURL(await res.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = "analytics.csv";
      link.click();
      URL.revokeObjectURL(url);
      toast("analytics.csv downloaded");
    } catch {
      toast("Could not export. Try again.", "error");
    }
  }
  const a = useApiQuery<Analytics>(["admin-analytics"], "/admin/analytics", { days });
  const tiles: [string, string][] = a.data
    ? [
        ["Searches", String(a.data.searches)],
        ["Searches with no results", String(a.data.empty_searches)],
        ["Listing views", String(a.data.listing_views)],
        ["Contacts", String(a.data.contacts)],
        ["Chats started", String(a.data.chats)],
        ["Requests posted", String(a.data.requests)],
        ["Orders", String(a.data.orders)],
        ["Confirmed deals", String(a.data.confirmed_deals)],
        ["Repeat buyers", String(a.data.repeat_buyers)],
        ["Active sellers", String(a.data.active_sellers)],
        ["Reviews", String(a.data.reviews)],
        ["Reports and disputes", String(a.data.reports + a.data.disputes)],
        ["Protected sales", naira(a.data.revenue_kobo)],
        ["Commission earned", naira(a.data.commission_kobo)],
      ]
    : [];
  return (
    <section aria-labelledby="analytics" className="mt-8 space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id="analytics" className="text-xl font-bold">Marketplace activity</h2>
        <div className="flex items-end gap-2">
          <div className="w-40">
            <Select label="Period" value={days} onChange={(e) => setDays(e.target.value)}>
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
            </Select>
          </div>
          <Button variant="secondary" onClick={() => void downloadAnalytics()}>Download CSV</Button>
        </div>
      </div>
      {a.isError && <ErrorState message={a.error.message} onRetry={() => void a.refetch()} />}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {tiles.map(([label, value]) => (
          <Card key={label}>
            <p className="text-xs text-muted">{label}</p>
            <p className="font-heading text-2xl font-extrabold">{value}</p>
          </Card>
        ))}
      </div>
      {a.data && a.data.top_empty_searches.length > 0 && (
        <div>
          <h3 className="mb-1 text-sm font-semibold">Most common searches with no results</h3>
          <ul className="flex flex-wrap gap-2 text-sm">
            {(a.data.top_empty_searches as { query: string; count: number }[]).map((q) => (
              <li key={q.query} className="rounded-full border border-line bg-white px-3 py-1">{q.query} ({q.count})</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

const tiles: { key: keyof Overview; label: string; href: string }[] = [
  { key: "users", label: "Users", href: "/admin/users" },
  { key: "sellers", label: "Sellers", href: "/admin/sellers" },
  { key: "verified_sellers", label: "Verified sellers", href: "/admin/sellers" },
  { key: "active_listings", label: "Active listings", href: "/admin/listings" },
  { key: "pending_verifications", label: "Pending verifications", href: "/admin/verification" },
  { key: "open_reports", label: "Open reports", href: "/admin/reports" },
  { key: "searches_without_results", label: "Searches with no results", href: "/admin/exports" },
];

export default function AdminOverview() {
  const overview = useApiQuery<Overview>(["admin-overview"], "/admin/overview");
  return (
    <>
      <PageHeader title="Admin overview" />
      {overview.isPending && (
        <div role="status" aria-label="Loading" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      )}
      {overview.isError && <ErrorState message={overview.error.message} onRetry={() => void overview.refetch()} />}
      {overview.data && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {tiles.map((t) => (
            <Link key={t.key} href={t.href} className="block rounded-card focus-visible:outline-offset-4">
              <Card className="h-full hover:border-ink">
                <p className="text-sm text-muted">{t.label}</p>
                <p className="font-heading text-4xl font-extrabold">{overview.data[t.key]}</p>
              </Card>
            </Link>
          ))}
        </div>
      )}
      <AnalyticsPanel />
    </>
  );
}
