import Link from "next/link";
import type { ReactNode } from "react";

export function Section({ title, href, children }: { title: string; href?: string; children: ReactNode }) {
  return (
    <section className="space-y-3" aria-labelledby={`section-${title.replace(/\W+/g, "-").toLowerCase()}`}>
      <div className="flex items-end justify-between gap-3">
        <h2 id={`section-${title.replace(/\W+/g, "-").toLowerCase()}`} className="text-xl font-extrabold md:text-2xl">{title}</h2>
        {href && (
          <Link href={href} className="inline-flex min-h-11 items-center text-sm font-semibold underline">
            See all
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}
