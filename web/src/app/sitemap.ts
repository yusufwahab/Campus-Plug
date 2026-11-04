import type { MetadataRoute } from "next";

export const dynamic = "force-dynamic";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function get<T>(path: string): Promise<T | null> {
  const res = await fetch(`${API}${path}`, { next: { revalidate: 300 } }).catch(() => null);
  return res?.ok ? ((await res.json()) as T) : null;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [listings, categories] = await Promise.all([
    get<{ items: { public_id: string; seller_slug: string }[] }>("/listings?size=60&sort=newest"),
    get<{ slug: string }[]>("/categories"),
  ]);
  const fixed = ["/", "/search", "/how-it-works", "/sell", "/help", "/contact", "/terms", "/privacy", "/seller-rules"].map((p) => ({ url: `${SITE}${p}` }));
  const cats = (categories ?? []).map((c) => ({ url: `${SITE}/categories/${c.slug}` }));
  const items = listings?.items ?? [];
  const shops = [...new Set(items.map((i) => i.seller_slug))].map((s) => ({ url: `${SITE}/shop/${s}` }));
  return [...fixed, ...cats, ...items.map((i) => ({ url: `${SITE}/listing/${i.public_id}` })), ...shops];
}
