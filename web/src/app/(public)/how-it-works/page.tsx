import type { Metadata } from "next";
import { ProsePage } from "@/components/layout/Prose";
import { Button } from "@/components/ui/Button";
import { steps } from "@/lib/content";

export const metadata: Metadata = { title: "How it works", description: "Discover, chat, pay safely, receive, confirm and review on Campus Plug." };

export default function HowItWorksPage() {
  return (
    <ProsePage title="How Campus Plug works" intro="From finding something to leaving a review, in five steps.">
      <ol className="space-y-3">
        {steps.map((s, i) => (
          <li key={s.title} className="flex gap-4 rounded-card border border-line bg-white p-4">
            <span className="grid size-10 shrink-0 place-items-center rounded-full bg-lime font-heading text-lg font-extrabold">{i + 1}</span>
            <div>
              <h2 className="text-lg font-bold">{s.title}</h2>
              <p className="text-sm text-muted">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap gap-2">
        <Button href="/search">Browse listings</Button>
        <Button href="/sell" variant="tertiary">
          Start selling
        </Button>
      </div>
    </ProsePage>
  );
}
