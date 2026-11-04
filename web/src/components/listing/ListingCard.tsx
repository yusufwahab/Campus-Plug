import clsx from "clsx";
import { BadgeCheck, Star } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { assetUrl } from "@/lib/api";
import { priceRange } from "@/lib/format";
import type { ListingCardData } from "@/lib/types";

const tints: Record<string, string> = { peach: "bg-peach", lilac: "bg-lilac", sky: "bg-sky", butter: "bg-butter", mint: "bg-mint" };

export function ListingCard({ item }: { item: ListingCardData }) {
  const image = assetUrl(item.image_url);
  return (
    <Link href={`/listing/${item.public_id}`} className="group block rounded-card focus-visible:outline-offset-4">
      <div className={clsx("relative aspect-square overflow-hidden rounded-card", tints[item.category_tint] ?? "bg-mint")}>
        {image ? (
          <Image src={image} alt={item.title} fill unoptimized sizes="(min-width:1024px) 20vw, (min-width:768px) 33vw, 50vw" className="object-cover transition group-hover:scale-105" />
        ) : (
          <span aria-hidden="true" className="absolute inset-0 grid place-items-center font-heading text-5xl font-extrabold text-ink/30">
            {item.title.charAt(0).toUpperCase()}
          </span>
        )}
        <span className="absolute left-2 top-2 flex flex-wrap gap-1">
          {item.sponsored && <Badge tone="info">Sponsored</Badge>}
          {item.type === "service" && <Badge tone="neutral">Service</Badge>}
        </span>
      </div>
      <div className="mt-2 space-y-0.5 px-1">
        <p className="font-heading text-lg font-bold leading-tight">{priceRange(item.price_kobo, item.price_max_kobo)}</p>
        <h3 className="line-clamp-2 font-sans text-sm font-medium leading-snug">{item.title}</h3>
        <p className="flex items-center gap-1 text-xs text-muted">
          <span className="truncate">{item.seller_name}</span>
          {item.seller_verified && <BadgeCheck className="size-4 shrink-0 text-forest" aria-label="Verified seller" />}
          {item.rating_avg !== null && (
            <span className="ml-auto flex shrink-0 items-center gap-0.5">
              <Star className="size-3.5 fill-butter text-ink" aria-hidden="true" />
              {item.rating_avg}
            </span>
          )}
        </p>
        {item.location_name && <p className="truncate text-xs text-muted">{item.location_name}</p>}
      </div>
    </Link>
  );
}

export function ListingGrid({ items }: { items: ListingCardData[] }) {
  return (
    <ul className="grid grid-cols-2 gap-x-3 gap-y-6 md:grid-cols-3 md:gap-x-4 lg:grid-cols-4 xl:grid-cols-5">
      {items.map((item) => (
        <li key={item.public_id}>
          <ListingCard item={item} />
        </li>
      ))}
    </ul>
  );
}
