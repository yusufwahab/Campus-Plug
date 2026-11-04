import { BadgeCheck, MapPin, Star } from "lucide-react";
import type { Metadata } from "next";
import { ShareButton } from "@/components/listing/ShareButton";
import { ShopTabs } from "@/components/listing/ShopTabs";
import { Badge } from "@/components/ui/Badge";
import { serverApi, serverApiOrNull } from "@/lib/server-api";
import type { components } from "@/lib/api-schema";

export const dynamic = "force-dynamic";

type ShopPage = { seller: components["schemas"]["SellerOut"]; products: components["schemas"]["ListingCard"][]; services: components["schemas"]["ListingCard"][] };

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const shop = await serverApiOrNull<ShopPage>(`/shops/${slug}`);
  if (!shop) return { title: "Shop not found" };
  const count = shop.products.length + shop.services.length;
  const title = `${shop.seller.name} on Campus Plug`;
  const description = `${shop.seller.bio || shop.seller.name}. ${count} listing${count === 1 ? "" : "s"} at ${shop.seller.campus_name ?? "your campus"}.`;
  const image = `${process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"}/shop/${slug}/og`;
  return { title, description, alternates: { canonical: `/shop/${slug}` }, openGraph: { title, description, images: [{ url: image, width: 1200, height: 630 }] }, twitter: { card: "summary_large_image", title, description, images: [image] } };
}

export default async function ShopPageView({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const { seller, products, services } = await serverApi<ShopPage>(`/shops/${slug}`);
  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 rounded-card bg-white p-5 md:flex-row md:items-center md:justify-between md:p-6">
        <div className="space-y-2">
          <h1 className="flex items-center gap-2 text-3xl font-extrabold">
            {seller.name}
            {seller.verification_status === "verified" && <BadgeCheck className="size-6 text-forest" aria-label="Verified seller" />}
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={seller.verification_status === "verified" ? "verified" : "pending"}>{seller.verification_status === "verified" ? "Verified student" : "Unverified"}</Badge>
            <Badge tone="info">{seller.trust_level.replace(/_/g, " ")}</Badge>
            <span className="text-xs text-muted">{seller.public_id}</span>
          </div>
          {seller.bio && <p className="max-w-xl text-sm">{seller.bio}</p>}
          <p className="flex flex-wrap items-center gap-3 text-sm text-muted">
            {seller.location_name && (
              <span className="flex items-center gap-1">
                <MapPin className="size-4" aria-hidden="true" /> {seller.location_name}
              </span>
            )}
            {seller.rating_avg != null && (
              <span className="flex items-center gap-1">
                <Star className="size-4 fill-butter text-ink" aria-hidden="true" /> {seller.rating_avg} ({seller.rating_count})
              </span>
            )}
            <span>{seller.confirmed_deals} confirmed deals</span>
          </p>
          {seller.holiday_mode && <Badge tone="pending">On holiday: listings are paused</Badge>}
        </div>
        <ShareButton path={`/shop/${seller.slug}`} title={`${seller.name} on Campus Plug`} label="Share shop" />
      </header>
      <ShopTabs products={products} services={services} slug={seller.slug} />
    </div>
  );
}
