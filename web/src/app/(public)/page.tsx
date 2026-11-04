import clsx from "clsx";
import { Sparkles } from "lucide-react";
import Link from "next/link";
import { ListingGrid } from "@/components/listing/ListingCard";
import { NearYou } from "@/components/listing/NearYou";
import { Section } from "@/components/listing/Section";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/States";
import { serverApi } from "@/lib/server-api";
import type { components } from "@/lib/api-schema";

export const dynamic = "force-dynamic";

type Category = components["schemas"]["CategoryOut"];
type Card = components["schemas"]["ListingCard"];
type Feed = { open_now: Card[]; new: Card[]; popular: Card[] };

const tints: Record<string, string> = { peach: "bg-peach", lilac: "bg-lilac", sky: "bg-sky", butter: "bg-butter", mint: "bg-mint" };

export default async function HomePage() {
  const [categories, feed] = await Promise.all([serverApi<Category[]>("/categories"), serverApi<Feed>("/home?campus=unilag")]);
  const empty = !feed.new.length;

  return (
    <div className="space-y-10">
      <section className="rounded-card bg-forest p-6 text-white md:p-12">
        <p className="text-sm font-semibold uppercase tracking-wide text-lime">UNILAG marketplace</p>
        <h1 className="mt-2 max-w-2xl text-4xl font-extrabold leading-tight md:text-6xl">Plug into trusted sellers on your campus.</h1>
        <p className="mt-4 max-w-xl text-white/80">Find food, fashion, gadgets and services from students near you. Chat, pay safely and review.</p>
        <div className="mt-6 flex flex-wrap gap-2">
          <Button href="/search">Browse listings</Button>
          <Button href="/sell" variant="tertiary" className="border-white text-white hover:bg-white/10">
            Start selling
          </Button>
        </div>
      </section>

      <nav aria-label="Categories">
        <ul className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-8">
          {categories.map((c) => (
            <li key={c.slug}>
              <Link href={`/categories/${c.slug}`} className={clsx("flex min-h-16 items-center justify-center rounded-card px-3 text-center font-heading text-base font-bold", tints[c.tint] ?? "bg-mint")}>
                {c.name}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      {empty ? (
        <EmptyState title="No listings yet" body="Be the first to list something on your campus." action={{ label: "Start selling", href: "/seller/start" }} />
      ) : (
        <>
          {feed.open_now.length > 0 && (
            <Section title="Open now" href="/search?open_now=true">
              <ListingGrid items={feed.open_now.slice(0, 5)} />
            </Section>
          )}
          <Section title="Near you" href="/search">
            <NearYou />
          </Section>
          <Section title="New listings" href="/search?sort=newest">
            <ListingGrid items={feed.new.slice(0, 10)} />
          </Section>
          <Section title="Popular" href="/search">
            <ListingGrid items={feed.popular.slice(0, 5)} />
          </Section>
        </>
      )}

      <section className="flex flex-col items-start gap-3 rounded-card bg-lilac p-6 md:flex-row md:items-center md:justify-between md:p-8">
        <div className="flex items-start gap-3">
          <Sparkles className="mt-1 size-6 shrink-0" aria-hidden="true" />
          <div>
            <h2 className="text-xl font-extrabold">Can&apos;t find it? Plug Me.</h2>
            <p className="text-sm">Tell the campus what you need and sellers will message you.</p>
          </div>
        </div>
        <Button href="/requests/new" variant="secondary">
          Post a request
        </Button>
      </section>
    </div>
  );
}
