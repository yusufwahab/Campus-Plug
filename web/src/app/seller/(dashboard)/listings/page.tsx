"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import type { BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmModal } from "@/components/ui/Modal";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import { naira } from "@/lib/format";
import type { ListingCardData } from "@/lib/types";

const tone: Record<string, BadgeTone> = { active: "verified", draft: "neutral", paused: "pending", sold_out: "danger", expired: "danger", removed: "danger" };

export default function SellerListings() {
  const client = useQueryClient();
  const toast = useToast();
  const listings = useQuery({ queryKey: ["seller-listings"], queryFn: () => api<ListingCardData[]>("/seller/listings") });
  const [confirmRemove, setConfirmRemove] = useState<ListingCardData | null>(null);
  const [confirmPause, setConfirmPause] = useState<ListingCardData | null>(null);
  const [busy, setBusy] = useState(false);

  async function act(item: ListingCardData, path: string, body: unknown, done: string) {
    setBusy(true);
    try {
      await api(`/listings/${item.public_id}/${path}`, { method: "POST", body });
      await client.invalidateQueries({ queryKey: ["seller-listings"] });
      toast(done);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Something went wrong", "error");
    } finally {
      setBusy(false);
      setConfirmRemove(null);
      setConfirmPause(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-extrabold md:text-3xl">Listings</h1>
        <Button href="/seller/listings/new">New listing</Button>
      </div>
      {listings.isPending && <CardGridSkeleton count={4} />}
      {listings.isError && <ErrorState message={listings.error.message} onRetry={() => void listings.refetch()} />}
      {listings.data && !listings.data.length && <EmptyState title="No listings yet" body="Publish your first listing in under a minute." action={{ label: "Add a listing", href: "/seller/listings/new" }} />}
      {listings.data && listings.data.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2">
          {listings.data.map((item) => (
            <li key={item.public_id}>
              <Card className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <Link href={`/listing/${item.public_id}`} className="line-clamp-2 font-semibold hover:underline">{item.title}</Link>
                    <p className="text-xs text-muted">{item.public_id}</p>
                  </div>
                  <Badge tone={tone[item.status] ?? "neutral"}>{item.status.replace("_", " ")}</Badge>
                </div>
                <p className="font-heading text-xl font-bold">{naira(item.price_kobo)}</p>
                <div className="flex flex-wrap gap-2">
                  <Button variant="tertiary" href={`/seller/listings/${item.public_id}/edit`}>Edit</Button>
                  {item.status === "active" && <Button variant="tertiary" onClick={() => setConfirmPause(item)}>Pause</Button>}
                  {["paused", "draft", "sold_out"].includes(item.status) && <Button variant="secondary" loading={busy} onClick={() => act(item, "status", { status: "active" }, "Listing is live")}>{item.status === "draft" ? "Publish" : "Resume"}</Button>}
                  {item.status === "active" && <Button variant="tertiary" loading={busy} onClick={() => act(item, "status", { status: "sold_out" }, "Marked as sold out")}>Sold out</Button>}
                  {["active", "expired"].includes(item.status) && <Button variant="tertiary" loading={busy} onClick={() => act(item, "still-available", undefined, "Renewed: still available")}>Still available</Button>}
                  <Button variant="danger" onClick={() => setConfirmRemove(item)}>Remove</Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
      <ConfirmModal open={!!confirmPause} title="Pause this listing?" body="Buyers will not see it until you resume it. Open orders are not affected." confirmLabel="Pause" loading={busy} onConfirm={() => confirmPause && act(confirmPause, "status", { status: "paused" }, "Listing paused")} onClose={() => setConfirmPause(null)} />
      <ConfirmModal open={!!confirmRemove} title="Remove this listing?" body="It disappears from the marketplace. This cannot be undone." confirmLabel="Remove" destructive loading={busy} onConfirm={() => confirmRemove && act(confirmRemove, "status", { status: "removed" }, "Listing removed")} onClose={() => setConfirmRemove(null)} />
    </div>
  );
}
