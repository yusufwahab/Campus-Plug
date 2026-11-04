"use client";
import { useQuery } from "@tanstack/react-query";
import { SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ListingGrid } from "@/components/listing/ListingCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { CardGridSkeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { nairaToKobo } from "@/lib/format";

type Result = { listings: components["schemas"]["ListingCard"][]; shops: components["schemas"]["SellerOut"][]; total: number; ask_campus: boolean };
type Category = components["schemas"]["CategoryOut"];
type Location = components["schemas"]["LocationOut"];

const RECENT_KEY = "cp_recent_searches";

function Filters({ params, onApply, categories, locations }: { params: URLSearchParams; onApply: (next: URLSearchParams) => void; categories: Category[]; locations: Location[] }) {
  const [draft, setDraft] = useState(() => new URLSearchParams(params));
  const set = (key: string, value: string) =>
    setDraft((cur) => {
      const next = new URLSearchParams(cur);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    });
  const get = (key: string) => draft.get(key) ?? "";
  const priceNaira = (key: string) => (get(key) ? String(Number(get(key)) / 100) : "");
  const setPrice = (key: string, value: string) => set(key, value ? String(nairaToKobo(Number(value))) : "");

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        onApply(draft);
      }}
    >
      <Select label="Type" value={get("type")} onChange={(e) => set("type", e.target.value)}>
        <option value="">Products and services</option>
        <option value="product">Products</option>
        <option value="service">Services</option>
      </Select>
      <Select label="Category" value={get("category")} onChange={(e) => set("category", e.target.value)}>
        <option value="">All categories</option>
        {categories.map((c) => (
          <option key={c.slug} value={c.slug}>
            {c.name}
          </option>
        ))}
      </Select>
      <Select label="Hall or area" value={get("location_id")} onChange={(e) => set("location_id", e.target.value)}>
        <option value="">Anywhere on campus</option>
        {locations.map((l) => (
          <option key={l.id} value={l.id}>
            {l.name}
          </option>
        ))}
      </Select>
      <div className="grid grid-cols-2 gap-2">
        <Input label="Min price (₦)" inputMode="numeric" value={priceNaira("min_price")} onChange={(e) => setPrice("min_price", e.target.value.replace(/\D/g, ""))} />
        <Input label="Max price (₦)" inputMode="numeric" value={priceNaira("max_price")} onChange={(e) => setPrice("max_price", e.target.value.replace(/\D/g, ""))} />
      </div>
      <Select label="Condition" value={get("condition")} onChange={(e) => set("condition", e.target.value)}>
        <option value="">Any</option>
        <option value="new">New</option>
        <option value="like_new">Like new</option>
        <option value="used">Used</option>
      </Select>
      <label className="flex min-h-11 items-center gap-3 text-sm font-semibold">
        <input type="checkbox" className="size-5 accent-forest" checked={get("verified") === "true"} onChange={(e) => set("verified", e.target.checked ? "true" : "")} />
        Verified sellers only
      </label>
      <label className="flex min-h-11 items-center gap-3 text-sm font-semibold">
        <input type="checkbox" className="size-5 accent-forest" checked={get("open_now") === "true"} onChange={(e) => set("open_now", e.target.checked ? "true" : "")} />
        Open now
      </label>
      <div className="flex gap-2">
        <Button type="submit" className="flex-1">
          Apply filters
        </Button>
        <Button variant="tertiary" onClick={() => onApply(new URLSearchParams({ q: params.get("q") ?? "" }))}>
          Clear
        </Button>
      </div>
    </form>
  );
}

function SearchView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);
  const q = params.get("q") ?? "";

  const categories = useQuery({ queryKey: ["categories"], queryFn: () => api<Category[]>("/categories") });
  const locations = useQuery({ queryKey: ["locations"], queryFn: () => api<Location[]>("/locations") });
  const results = useQuery({
    queryKey: ["search", params.toString()],
    queryFn: () => api<Result>("/search", { query: Object.fromEntries(params.entries()) }),
  });

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate from localStorage after mount
    setRecent(JSON.parse(window.localStorage.getItem(RECENT_KEY) ?? "[]") as string[]);
  }, []);

  useEffect(() => {
    if (!q) return;
    const next = [q, ...(JSON.parse(window.localStorage.getItem(RECENT_KEY) ?? "[]") as string[]).filter((r) => r !== q)].slice(0, 6);
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  }, [q]);

  const apply = (next: URLSearchParams) => {
    router.push(`${pathname}?${next.toString()}`);
    setFiltersOpen(false);
  };
  const activeFilters = [...params.keys()].filter((k) => !["q", "sort"].includes(k)).length;
  const filtersUi = categories.data && locations.data && <Filters key={params.toString()} params={params} onApply={apply} categories={categories.data} locations={locations.data} />;

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside className="hidden lg:block">
        <h2 className="mb-3 text-lg font-bold">Filters</h2>
        {filtersUi}
      </aside>

      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-extrabold">{q ? `Results for “${q}”` : "Browse everything"}</h1>
          <div className="flex items-center gap-2">
            <Button variant="tertiary" className="lg:hidden" onClick={() => setFiltersOpen(true)}>
              <SlidersHorizontal className="size-4" aria-hidden="true" />
              Filters{activeFilters ? ` (${activeFilters})` : ""}
            </Button>
            <div className="w-44">
              <Select
                label="Sort by"
                value={params.get("sort") ?? "relevance"}
                onChange={(e) => {
                  const next = new URLSearchParams(params);
                  next.set("sort", e.target.value);
                  apply(next);
                }}
              >
                <option value="relevance">Best match</option>
                <option value="newest">Newest</option>
                <option value="price_asc">Price: low to high</option>
                <option value="price_desc">Price: high to low</option>
              </Select>
            </div>
          </div>
        </div>

        {!q && recent.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted">Recent:</span>
            {recent.map((r) => (
              <Link key={r} href={`/search?q=${encodeURIComponent(r)}`} className="inline-flex min-h-11 items-center rounded-full border border-line bg-white px-4 text-sm">
                {r}
              </Link>
            ))}
          </div>
        )}

        {results.isPending && <CardGridSkeleton />}
        {results.isError && <ErrorState message={results.error.message} onRetry={() => void results.refetch()} />}
        {results.data && (
          <>
            {results.data.shops.length > 0 && (
              <ul className="flex flex-wrap gap-2" aria-label="Matching shops">
                {results.data.shops.map((s) => (
                  <li key={s.slug}>
                    <Link href={`/shop/${s.slug}`} className="inline-flex min-h-11 items-center gap-2 rounded-full bg-white px-4 text-sm font-semibold">
                      {s.name} <Badge tone="neutral">Shop</Badge>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {results.data.listings.length > 0 ? (
              <ListingGrid items={results.data.listings} />
            ) : results.data.ask_campus ? (
              <EmptyState title={`Nobody is selling “${q}” yet`} body="Ask the campus. Matching sellers will message you." action={{ label: "Ask campus for this", href: `/requests/new?q=${encodeURIComponent(q)}` }} />
            ) : (
              <EmptyState title="No matches" body="Try removing a filter or searching for something broader." action={{ label: "Clear filters", href: q ? `/search?q=${encodeURIComponent(q)}` : "/search" }} />
            )}
          </>
        )}
      </div>

      <Modal open={filtersOpen} title="Filters" onClose={() => setFiltersOpen(false)}>
        {filtersUi}
      </Modal>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense>
      <SearchView />
    </Suspense>
  );
}
