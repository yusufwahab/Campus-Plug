"use client";
import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { NavItem } from "@/lib/nav";

export function isActive(pathname: string, href: string) {
  return href === "/" || href === "/seller" || href === "/admin" ? pathname === href : pathname.startsWith(href);
}

/** Mobile-only bottom navigation. Hidden from 768px up. */
export function BottomNav({ items, label }: { items: NavItem[]; label: string }) {
  const pathname = usePathname();
  return (
    <nav aria-label={label} className="pb-safe fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white md:hidden">
      <ul className="grid" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
        {items.map(({ href, label: text, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={clsx("flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px] font-semibold", active ? "text-ink" : "text-muted")}
              >
                <span className={clsx("grid h-7 w-12 place-items-center rounded-full", active && "bg-lime")}>
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                {text}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
