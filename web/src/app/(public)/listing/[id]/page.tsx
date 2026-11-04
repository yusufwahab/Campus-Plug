import { BadgeCheck, MapPin, ShieldCheck, Star } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Gallery } from "@/components/listing/Gallery";
import { BuyButton } from "@/components/listing/BuyButton";
import { MessageButton } from "@/components/listing/MessageButton";
import { ReportButton } from "@/components/listing/ReportButton";
import { SaveButton } from "@/components/listing/SaveButton";
import { ShareButton } from "@/components/listing/ShareButton";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { assetUrl } from "@/lib/api";
import { naira, priceRange } from "@/lib/format";
import { serverApi, serverApiOrNull } from "@/lib/server-api";
import type { ListingDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
const tints: Record<string, string> = { peach: "bg-peach", lilac: "bg-lilac", sky: "bg-sky", butter: "bg-butter", mint: "bg-mint" };

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const listing = await serverApiOrNull<ListingDetail>(`/listings/${id}`);
  if (!listing) return { title: "Listing not found" };
  const price = priceRange(listing.price_kobo, listing.price_max_kobo);
  const title = `${listing.title} - ${price}`;
  const description = `${listing.description.slice(0, 140) || listing.title} Sold by ${listing.seller_name} on Campus Plug.`;
  const image = assetUrl(listing.images[0]?.url) ?? `${SITE}/listing/${id}/og`;
  return {
    title,
    description,
    alternates: { canonical: `/listing/${listing.public_id}` },
    openGraph: { title, description, type: "website", url: `/listing/${listing.public_id}`, images: [{ url: image, width: 1200, height: 630, alt: listing.title }] },
    twitter: { card: "summary_large_image", title, description, images: [image] },
  };
}

function Detail({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex justify-between gap-4 border-b border-line py-2 text-sm last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-semibold">{value}</dd>
    </div>
  );
}

export default async function ListingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const l = await serverApi<ListingDetail>(`/listings/${id}`);
  const seller = l.seller;
  const price = priceRange(l.price_kobo, l.price_max_kobo);
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": l.type === "service" ? "Service" : "Product",
    name: l.title,
    description: l.description,
    image: l.images.map((i) => assetUrl(i.url)),
    sku: l.public_id,
    offers: { "@type": "Offer", priceCurrency: "NGN", price: (l.price_kobo / 100).toFixed(2), availability: l.quantity > 0 ? "https://schema.org/InStock" : "https://schema.org/OutOfStock", seller: { "@type": "Organization", name: seller.name } },
  };

  return (
    <article className="grid gap-6 pb-24 lg:grid-cols-[minmax(0,1fr)_380px] lg:pb-0">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />
      <div className="space-y-6">
        <Gallery images={l.images} title={l.title} tint={tints[l.category_tint] ?? "bg-mint"} />

        <Card className="space-y-3">
          <h2 className="text-lg font-bold">About this {l.type}</h2>
          <p className="whitespace-pre-line text-sm leading-relaxed">{l.description || "The seller has not added a description."}</p>
          <dl>
            <Detail label="Listing ID" value={l.public_id} />
            <Detail label="Condition" value={l.condition?.replace("_", " ")} />
            <Detail label="In stock" value={l.type === "product" ? l.quantity : null} />
            <Detail label="Collection" value={l.fulfilment === "both" ? "Pickup or delivery" : l.fulfilment === "delivery" ? "Delivery" : "Pickup"} />
            <Detail label="Delivery fee" value={l.delivery_fee_kobo ? naira(l.delivery_fee_kobo) : null} />
            <Detail label="Availability" value={l.availability} />
            <Detail label="Duration" value={l.duration_min ? `${l.duration_min} min` : null} />
            <Detail label="Booking deposit" value={l.deposit_kobo ? naira(l.deposit_kobo) : null} />
            <Detail label="Pre-order" value={l.preorder ? "Yes" : null} />
          </dl>
          {l.packages.length > 0 && (
            <div>
              <h3 className="mt-2 font-bold">Packages</h3>
              <ul className="mt-1 space-y-1 text-sm">
                {(l.packages as { name: string; price_kobo: number }[]).map((p) => (
                  <li key={p.name} className="flex justify-between">
                    <span>{p.name}</span>
                    <span className="font-semibold">{naira(p.price_kobo)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
        <Card className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="neutral">{l.category_slug}</Badge>
            {l.negotiable && <Badge tone="info">Negotiable</Badge>}
            {l.status === "sold_out" && <Badge tone="danger">Sold out</Badge>}
          </div>
          <h1 className="text-2xl font-extrabold leading-tight">{l.title}</h1>
          <p className="font-heading text-3xl font-extrabold">{price}</p>
          {l.location_name && (
            <p className="flex items-center gap-1 text-sm text-muted">
              <MapPin className="size-4" aria-hidden="true" /> {l.location_name}, {l.campus_name}
            </p>
          )}
          <div className="hidden gap-2 lg:grid">
            <BuyButton listingId={l.public_id} type={l.type} priceKobo={l.price_kobo} depositKobo={l.deposit_kobo} fulfilment={l.fulfilment} deliveryFeeKobo={l.delivery_fee_kobo} quantityAvailable={l.quantity} preorder={l.preorder} sellerVerified={seller.verification_status === "verified"} className="w-full" />
            <MessageButton listingId={l.public_id} className="w-full" />
          </div>
          <div className="flex flex-wrap gap-2">
            <SaveButton publicId={l.public_id} />
            <ShareButton path={`/listing/${l.public_id}`} title={l.title} />
            <ReportButton targetType="listing" targetId={l.public_id} />
          </div>
        </Card>

        <Card className="space-y-2">
          <Link href={`/shop/${seller.slug}`} className="flex items-center gap-1 font-heading text-lg font-bold hover:underline">
            {seller.name}
            {seller.verification_status === "verified" && <BadgeCheck className="size-5 text-forest" aria-label="Verified seller" />}
          </Link>
          <div className="flex flex-wrap gap-2">
            <Badge tone={seller.verification_status === "verified" ? "verified" : "pending"}>{seller.verification_status === "verified" ? "Verified student" : "Unverified"}</Badge>
            <Badge tone="info">{seller.trust_level.replace(/_/g, " ")}</Badge>
          </div>
          <p className="flex items-center gap-3 text-sm text-muted">
            {seller.rating_avg !== null && seller.rating_avg !== undefined ? (
              <span className="flex items-center gap-1">
                <Star className="size-4 fill-butter text-ink" aria-hidden="true" /> {seller.rating_avg} ({seller.rating_count})
              </span>
            ) : (
              <span>No reviews yet</span>
            )}
            <span>{seller.confirmed_deals} confirmed deals</span>
          </p>
          <p className="flex items-start gap-1 text-xs text-muted">
            <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            Pay in the app for protection. Cash and direct transfers are marked &quot;Not protected&quot;.
          </p>
        </Card>
      </aside>
      <div className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-30 flex items-center gap-3 border-t border-line bg-white p-3 md:bottom-0 lg:hidden">
        <p className="min-w-0 flex-1 truncate font-heading text-lg font-extrabold">{price}</p>
        <MessageButton listingId={l.public_id} className="flex-1" />
        <BuyButton listingId={l.public_id} type={l.type} priceKobo={l.price_kobo} depositKobo={l.deposit_kobo} fulfilment={l.fulfilment} deliveryFeeKobo={l.delivery_fee_kobo} quantityAvailable={l.quantity} preorder={l.preorder} sellerVerified={seller.verification_status === "verified"} className="flex-1" />
      </div>
    </article>
  );
}
