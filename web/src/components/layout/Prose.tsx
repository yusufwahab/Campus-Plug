import type { ReactNode } from "react";
import type { Block } from "@/lib/content";

export function ProsePage({ title, intro, blocks, children }: { title: string; intro?: string; blocks?: Block[]; children?: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl space-y-6 py-4">
      <header>
        <h1 className="text-4xl font-extrabold">{title}</h1>
        {intro && <p className="mt-2 text-lg text-muted">{intro}</p>}
      </header>
      {blocks?.map((b) => (
        <section key={b.heading} className="space-y-2">
          <h2 className="text-xl font-bold">{b.heading}</h2>
          {b.body.map((p) => (
            <p key={p} className="leading-relaxed">
              {p}
            </p>
          ))}
        </section>
      ))}
      {children}
    </article>
  );
}
