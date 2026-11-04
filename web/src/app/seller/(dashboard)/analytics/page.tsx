"use client";
import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import type { components } from "@/lib/api-schema";
import { useApiQuery } from "@/lib/hooks";

type Analytics = components["schemas"]["SellerAnalytics"];

export default function SellerAnalytics() {
  const [days, setDays] = useState("30");
  const data = useApiQuery<Analytics>(["seller-analytics"], "/seller/analytics", { days });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-extrabold md:text-3xl">Analytics</h1>
        <div className="w-40">
          <Select label="Period" value={days} onChange={(e) => setDays(e.target.value)}>
            <option value="7">Last 7 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
          </Select>
        </div>
      </div>
      {data.isPending ? (
        <div role="status" aria-label="Loading" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      ) : data.isError ? (
        <ErrorState message={data.error.message} onRetry={() => void data.refetch()} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(
              [
                ["Listing views", String(data.data.listing_views)],
                ["Contacts", String(data.data.contacts)],
                ["Paid orders", String(data.data.orders)],
                ["Confirmed deals", String(data.data.confirmed_deals)],
                ["Orders per view", `${data.data.conversion_pct}%`],
                ["Rating", data.data.rating_avg === null || data.data.rating_avg === undefined ? "No reviews yet" : `${data.data.rating_avg} from ${data.data.reviews} reviews`],
              ] as const
            ).map(([label, value]) => (
              <Card key={label}>
                <p className="text-sm text-muted">{label}</p>
                <p className="font-heading text-3xl font-extrabold">{value}</p>
              </Card>
            ))}
          </div>
          <h2 className="text-lg font-bold">Most viewed listings</h2>
          {data.data.top_listings.length === 0 ? (
            <p className="text-sm text-muted">Views appear here once buyers open your listings.</p>
          ) : (
            <ol className="space-y-2">
              {(data.data.top_listings as { public_id: string; title: string; views: number }[]).map((l) => (
                <li key={l.public_id} className="flex justify-between rounded-card border border-line bg-white p-3 text-sm">
                  <span>{l.title}</span>
                  <span className="text-muted">{l.views} views</span>
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </div>
  );
}
