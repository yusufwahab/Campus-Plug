import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

export function Section({ title, subtitle, href, children }: { title: string; subtitle?: string; href?: string; children: ReactNode }) {
  const id = `section-${title.replace(/\W+/g, "-").toLowerCase()}`;
  return (
    <section className="space-y-4" aria-labelledby={id}>
      <div className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 id={id} className="font-heading text-2xl font-extrabold leading-tight md:text-3xl">
            {title}
          </h2>
          {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
        </div>
        {href && (
          <Link
            href={href}
            className="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-full border border-line bg-white px-4 text-sm font-semibold transition hover:border-ink hover:bg-lime"
          >
            See all
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}
