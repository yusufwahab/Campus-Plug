"use client";
import { useQuery } from "@tanstack/react-query";
import { ListingGrid } from "@/components/listing/ListingCard";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";
import type { ListingCardData } from "@/lib/types";

function Saved() {
  const saved = useQuery({ queryKey: ["saved"], queryFn: () => api<ListingCardData[]>("/saved") });
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-extrabold">Saved</h1>
      {saved.isPending && <CardGridSkeleton count={5} />}
      {saved.isError && <ErrorState message={saved.error.message} onRetry={() => void saved.refetch()} />}
      {saved.data && (saved.data.length ? <ListingGrid items={saved.data} /> : <EmptyState title="Nothing saved yet" body="Tap Save on any listing to keep it here." action={{ label: "Browse listings", href: "/search" }} />)}
    </div>
  );
}

export default function SavedPage() {
  return (
    <RequireAuth>
      <Saved />
    </RequireAuth>
  );
}
