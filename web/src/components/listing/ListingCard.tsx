import clsx from "clsx";
import { BadgeCheck, MapPin, Star } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { assetUrl } from "@/lib/api";
import { priceRange } from "@/lib/format";
import type { ListingCardData } from "@/lib/types";

const tints: Record<string, string> = { peach: "bg-peach", lilac: "bg-lilac", sky: "bg-sky", butter: "bg-butter", mint: "bg-mint" };

export function ListingCard({ item }: { item: ListingCardData }) {
  const image = assetUrl(item.image_url);
  return (
    <Link
      href={`/listing/${item.public_id}`}
      className={clsx(
        "group flex h-full flex-col overflow-hidden rounded-card border border-line bg-white",
        "transition duration-200 hover:border-forest/30 hover:shadow-[0_14px_32px_-14px_rgba(22,58,44,0.4)] motion-safe:hover:-translate-y-1",
        "focus-visible:outline-offset-4",
      )}
    >
      <div className={clsx("relative aspect-[4/3] overflow-hidden", tints[item.category_tint] ?? "bg-mint")}>
        {image ? (
          <Image
            src={image}
            alt={item.title}
            fill
            unoptimized
            sizes="(min-width:1280px) 20vw, (min-width:1024px) 25vw, (min-width:768px) 33vw, 50vw"
            className="object-cover motion-safe:transition motion-safe:duration-500 motion-safe:group-hover:scale-105"
          />
        ) : (
          <span aria-hidden="true" className="absolute inset-0 grid place-items-center font-heading text-6xl font-extrabold text-ink/25">
            {item.title.charAt(0).toUpperCase()}
          </span>
        )}
        <span className="absolute left-2.5 top-2.5 flex flex-wrap gap-1.5">
          {item.sponsored && <span className="rounded-full bg-lime px-2.5 py-1 text-xs font-bold text-forest shadow-sm">Sponsored</span>}
          {item.type === "service" && <span className="rounded-full bg-white/95 px-2.5 py-1 text-xs font-semibold text-ink shadow-sm">Service</span>}
        </span>
        {item.location_name && (
          <span className="absolute bottom-2.5 left-2.5 flex max-w-[calc(100%-1.25rem)] items-center gap-1 rounded-full bg-white/95 px-2.5 py-1 text-xs font-medium text-ink shadow-sm">
            <MapPin className="size-3.5 shrink-0 text-forest" aria-hidden="true" />
            <span className="truncate">{item.location_name}</span>
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-3.5">
        <h3 className="line-clamp-2 min-h-[2.5rem] font-sans text-sm font-medium leading-snug text-ink">{item.title}</h3>
        <p className="font-heading text-xl font-extrabold leading-none text-forest">{priceRange(item.price_kobo, item.price_max_kobo)}</p>
        <div className="mt-auto flex items-center gap-2 border-t border-line pt-2.5 text-xs text-muted">
          <span aria-hidden="true" className="grid size-6 shrink-0 place-items-center rounded-full bg-forest text-[11px] font-bold text-lime">
            {item.seller_name.charAt(0).toUpperCase()}
          </span>
          <span className="truncate font-medium text-ink">{item.seller_name}</span>
          {item.seller_verified && <BadgeCheck className="size-4 shrink-0 text-forest" aria-label="Verified seller" />}
          {item.rating_avg !== null && (
            <span className="ml-auto flex shrink-0 items-center gap-0.5 font-semibold text-ink">
              <Star className="size-3.5 fill-butter text-ink" aria-hidden="true" />
              {item.rating_avg}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

/** A responsive grid of cards, used on search, categories and shop pages. */
export function ListingGrid({ items }: { items: ListingCardData[] }) {
  return (
    <ul className="grid grid-cols-2 gap-3 md:grid-cols-3 md:gap-4 lg:grid-cols-4 xl:grid-cols-5">
      {items.map((item) => (
        <li key={item.public_id}>
          <ListingCard item={item} />
        </li>
      ))}
    </ul>
  );
}

/** Home page rows: swipe sideways on phones, a normal grid from tablets up. */
export function ListingRail({ items }: { items: ListingCardData[] }) {
  return (
    <ul className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-3 [scrollbar-width:none] md:grid md:grid-cols-3 md:gap-4 md:overflow-visible md:pb-0 lg:grid-cols-4 xl:grid-cols-5 [&::-webkit-scrollbar]:hidden">
      {items.map((item) => (
        <li key={item.public_id} className="w-[58vw] max-w-60 shrink-0 snap-start md:w-auto md:max-w-none">
          <ListingCard item={item} />
        </li>
      ))}
    </ul>
  );
}
