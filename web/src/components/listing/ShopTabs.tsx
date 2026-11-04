"use client";
import clsx from "clsx";
import { useState } from "react";
import { Stars } from "@/components/reviews/Stars";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/States";
import type { components } from "@/lib/api-schema";
import { useApiQuery } from "@/lib/hooks";
import type { ListingCardData } from "@/lib/types";
import { ListingGrid } from "./ListingCard";

const tabs = ["Products", "Services", "Reviews"] as const;

type Review = components["schemas"]["ReviewOut"];

function ShopReviews({ slug }: { slug: string }) {
  const reviews = useApiQuery<Review[]>(["shop-reviews", slug], `/shops/${slug}/reviews`);
  if (reviews.isPending) return <p role="status" className="text-sm text-muted">Loading reviews</p>;
  if (reviews.isError || reviews.data.length === 0) return <EmptyState title="No reviews yet" body="Reviews from confirmed orders appear here." />;
  return (
    <ul className="space-y-3">
      {reviews.data.map((r) => (
        <li key={r.id} className="space-y-1 rounded-card border border-line bg-white p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Stars rating={r.rating} />
            <span className="text-sm font-semibold">{r.buyer_first_name}</span>
            {!r.confirmed_deal && <Badge tone="neutral">Unconfirmed deal</Badge>}
          </div>
          {r.body && <p className="text-sm">{r.body}</p>}
          {r.reply && <p className="rounded-input bg-surface p-3 text-sm"><strong>Seller reply:</strong> {r.reply}</p>}
        </li>
      ))}
    </ul>
  );
}

export function ShopTabs({ products, services, slug }: { products: ListingCardData[]; services: ListingCardData[]; slug: string }) {
  const [tab, setTab] = useState<(typeof tabs)[number]>("Products");
  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="Shop sections" className="flex gap-2">
        {tabs.map((t) => (
          <button
            key={t}
            role="tab"
            id={`tab-${t}`}
            aria-selected={tab === t}
            aria-controls={`panel-${t}`}
            onClick={() => setTab(t)}
            className={clsx("min-h-11 rounded-full px-5 text-sm font-semibold", tab === t ? "bg-ink text-white" : "border border-line bg-white")}
          >
            {t}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "Products" && (products.length ? <ListingGrid items={products} /> : <EmptyState title="No products yet" body="This shop has not listed any products." />)}
        {tab === "Services" && (services.length ? <ListingGrid items={services} /> : <EmptyState title="No services yet" body="This shop has not listed any services." />)}
        {tab === "Reviews" && <ShopReviews slug={slug} />}
      </div>
    </div>
  );
}
