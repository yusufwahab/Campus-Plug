import "server-only";
import { notFound } from "next/navigation";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/**
 * Fetch public data on the server so pages render with real content for crawlers and link previews.
 * Never cached: listings, categories, policies and announcements are edited by sellers and Admin and must show immediately.
 */
export async function serverApi<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`API ${res.status} for ${path}`);
  return (await res.json()) as T;
}

/** Same as serverApi but returns null on any failure (used by metadata generators and optional content). */
export async function serverApiOrNull<T>(path: string): Promise<T | null> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" }).catch(() => null);
  if (!res || !res.ok) {
    // Path and status only (no secrets), so the host's runtime logs show why a page could not load its data.
    console.error(`API request failed: ${path} ${res ? `status ${res.status}` : "could not connect (check NEXT_PUBLIC_API_URL)"}`);
    return null;
  }
  return (await res.json()) as T;
}
