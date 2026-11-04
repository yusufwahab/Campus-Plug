"use client";
import { useQuery } from "@tanstack/react-query";
import { usePlace } from "@/components/layout/LocationSelector";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { ListingGrid } from "./ListingCard";

type Page = components["schemas"]["ListingPage"];

/** Listings in the visitor's chosen hall. The choice lives in the browser, so this is fetched on the client. */
export function NearYou() {
  const [place] = usePlace();
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ["near-you", place.campusSlug, place.locationId],
    queryFn: () => api<Page>("/listings", { query: { campus: place.campusSlug, location_id: place.locationId, size: 5 } }),
    enabled: place.locationId !== null,
  });

  if (place.locationId === null) {
    return <p className="rounded-card bg-white p-4 text-sm text-muted">Choose your hall in the location selector to see sellers closest to you.</p>;
  }
  if (isPending) return <CardGridSkeleton count={5} />;
  if (isError) return <ErrorState message="Could not load nearby listings." onRetry={() => void refetch()} />;
  if (!data.items.length) return <p className="rounded-card bg-white p-4 text-sm text-muted">Nothing listed in {place.locationName} yet. Try browsing the whole campus.</p>;
  return <ListingGrid items={data.items} />;
}
