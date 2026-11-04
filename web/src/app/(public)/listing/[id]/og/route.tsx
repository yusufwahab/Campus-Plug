import { ImageResponse } from "next/og";
import { priceRange } from "@/lib/format";
import { serverApiOrNull } from "@/lib/server-api";
import type { ListingDetail } from "@/lib/types";

/** Open Graph card for listings without a photo: title, price and seller on brand colours. */
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const l = await serverApiOrNull<ListingDetail>(`/listings/${id}`);
  const title = l?.title ?? "Campus Plug";
  const price = l ? priceRange(l.price_kobo, l.price_max_kobo) : "";
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", background: "#163A2C", color: "white", padding: 72 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 36, color: "#C9F26C" }}>Campus Plug</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ fontSize: 76, fontWeight: 800, lineHeight: 1.05 }}>{title.slice(0, 70)}</div>
          <div style={{ fontSize: 64, color: "#C9F26C", fontWeight: 800 }}>{price}</div>
        </div>
        <div style={{ fontSize: 32, opacity: 0.85 }}>{l ? `Sold by ${l.seller_name}` : "Trusted products and services on your campus"}</div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}
