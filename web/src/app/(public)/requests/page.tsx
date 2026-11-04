"use client";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { RequestCard } from "@/components/requests/RequestCard";

type Req = components["schemas"]["RequestOut"];
type Category = components["schemas"]["CategoryOut"];

export default function RequestsPage() {
  const [category, setCategory] = useState("");
  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/categories") });
  const feed = useQuery({ queryKey: ["requests", category], queryFn: () => api<Req[]>("/requests", { query: { category } }), refetchInterval: 15000 });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold">Requests</h1>
          <p className="text-sm text-muted">Students asking the campus for something. Sellers reply in chat.</p>
        </div>
        <div className="flex items-end gap-2">
          <div className="w-44">
            <Select label="Category" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {categories.data?.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
            </Select>
          </div>
          <Button href="/requests/new">Plug Me</Button>
        </div>
      </div>
      {feed.isPending && <div role="status" aria-label="Loading" className="grid gap-3 md:grid-cols-2">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28" />)}</div>}
      {feed.isError && <ErrorState message={feed.error.message} onRetry={() => void feed.refetch()} />}
      {feed.data && !feed.data.length && <EmptyState title="No open requests" body="Need something? Post a Plug Me request and sellers will message you." action={{ label: "Post a request", href: "/requests/new" }} />}
      {feed.data && feed.data.length > 0 && (
        <ul className="grid gap-3 md:grid-cols-2">
          {feed.data.map((r) => <li key={r.id}><RequestCard r={r} /></li>)}
        </ul>
      )}
    </div>
  );
}
