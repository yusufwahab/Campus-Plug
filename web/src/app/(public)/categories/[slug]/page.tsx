import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ListingGrid } from "@/components/listing/ListingCard";
import { EmptyState } from "@/components/ui/States";
import { serverApi } from "@/lib/server-api";
import type { components } from "@/lib/api-schema";

export const dynamic = "force-dynamic";

type Category = components["schemas"]["CategoryOut"];
type Page = components["schemas"]["ListingPage"];

async function categoryFor(slug: string) {
  const all = await serverApi<Category[]>("/categories");
  const found = all.find((c) => c.slug === slug);
  if (!found) notFound();
  return found;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const category = await categoryFor((await params).slug);
  return { title: `${category.name} at UNILAG`, description: `Browse ${category.name.toLowerCase()} from students and sellers at UNILAG.`, alternates: { canonical: `/categories/${category.slug}` } };
}

export default async function CategoryPage({ params }: { params: Promise<{ slug: string }> }) {
  const category = await categoryFor((await params).slug);
  const page = await serverApi<Page>(`/listings?category=${category.slug}&campus=unilag&size=40`);
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-extrabold">{category.name}</h1>
      {page.items.length ? (
        <ListingGrid items={page.items} />
      ) : (
        <EmptyState title={`No ${category.name.toLowerCase()} listings yet`} body="Check back soon or post a request and sellers will come to you." action={{ label: "Post a request", href: "/requests/new" }} />
      )}
    </div>
  );
}
