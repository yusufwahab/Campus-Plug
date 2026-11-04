import { ImageResponse } from "next/og";
import { serverApiOrNull } from "@/lib/server-api";
import type { components } from "@/lib/api-schema";

type ShopPage = { seller: components["schemas"]["SellerOut"]; products: unknown[]; services: unknown[] };

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const shop = await serverApiOrNull<ShopPage>(`/shops/${slug}`);
  const name = shop?.seller.name ?? "Campus Plug";
  const count = shop ? shop.products.length + shop.services.length : 0;
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", background: "#163A2C", color: "white", padding: 72 }}>
        <div style={{ fontSize: 36, color: "#C9F26C" }}>Campus Plug</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 84, fontWeight: 800, lineHeight: 1.05 }}>{name.slice(0, 50)}</div>
          <div style={{ fontSize: 40, color: "#C9F26C" }}>{count} listings on campus</div>
        </div>
        <div style={{ fontSize: 32, opacity: 0.85 }}>{shop?.seller.campus_name ?? "Trusted products and services on your campus"}</div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}
