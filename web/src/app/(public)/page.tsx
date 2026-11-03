import { Button } from "@/components/ui/Button";

export default function HomePage() {
  return (
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
  );
}
