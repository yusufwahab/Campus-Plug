import Link from "next/link";
import { Logo } from "@/components/ui/Logo";

const columns = [
  { title: "Campus Plug", links: [["How it works", "/how-it-works"], ["Start selling", "/sell"], ["Help", "/help"], ["Contact", "/contact"]] },
  { title: "Trust", links: [["Seller rules", "/seller-rules"], ["Banned items", "/banned-items"], ["Terms", "/terms"], ["Privacy", "/privacy"]] },
] as const;

export function Footer() {
  return (
    <footer className="mt-16 rounded-card bg-forest p-6 text-white md:p-8">
      <div className="grid gap-8 md:grid-cols-3">
        <div>
          <Logo />
          <p className="mt-3 max-w-xs text-sm text-white/80">Trusted products and services on your campus. Launching at UNILAG.</p>
        </div>
        {columns.map((c) => (
          <nav key={c.title} aria-label={c.title}>
            <h2 className="text-sm font-bold uppercase tracking-wide text-lime">{c.title}</h2>
            <ul className="mt-3 space-y-1">
              {c.links.map(([label, href]) => (
                <li key={href}>
                  <Link href={href} className="inline-flex min-h-11 items-center text-sm hover:underline">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <p className="mt-8 text-xs text-white/70">© {new Date().getFullYear()} Campus Plug</p>
    </footer>
  );
}
