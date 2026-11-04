"use client";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { ListingForm } from "@/components/seller/ListingForm";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { ListingDetail } from "@/lib/types";

export default function EditListingPage() {
  const { id } = useParams<{ id: string }>();
  const listing = useQuery({ queryKey: ["seller-listing", id], queryFn: () => api<ListingDetail>(`/seller/listings/${id}`) });
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-extrabold md:text-3xl">Edit listing</h1>
      {listing.isPending && <div role="status" aria-label="Loading" className="space-y-3"><Skeleton className="h-40" /><Skeleton className="h-40" /></div>}
      {listing.isError && <ErrorState message={listing.error.message} onRetry={() => void listing.refetch()} />}
      {listing.data && <ListingForm existing={listing.data} />}
    </div>
  );
}
