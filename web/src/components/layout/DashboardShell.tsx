"use client";
import clsx from "clsx";
import { Menu, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { ReactNode } from "react";
import { Modal } from "@/components/ui/Modal";
import { Logo } from "@/components/ui/Logo";
import { adminNav, sellerMobileHrefs, sellerNav } from "@/lib/nav";
import { BottomNav, isActive } from "./BottomNav";

type Props = {
  /** Seller gets a bottom bar plus a More drawer; admin uses a menu drawer only. */
  kind: "seller" | "admin";
  children: ReactNode;
};

/**
 * Mobile: top bar + bottom nav (seller) with a More drawer, or a menu drawer (admin).
 * Tablet (768-1023): icon rail with labels. Desktop (1024+): full sidebar.
 */
export function DashboardShell({ kind, children }: Props) {
  const title = kind === "seller" ? "Seller" : "Admin";
  const admin = kind === "admin";
  const items = kind === "seller" ? sellerNav : adminNav;
  const mobileHrefs = kind === "seller" ? sellerMobileHrefs : undefined;
  const pathname = usePathname();
  const [drawer, setDrawer] = useState(false);
  const mobileItems = mobileHrefs ? items.filter((i) => mobileHrefs.includes(i.href)) : [];
  const moreItems = mobileHrefs ? items.filter((i) => !mobileHrefs.includes(i.href)) : items;

  const list = (variant: "rail" | "full" | "drawer") => (
    <ul className="space-y-1">
      {items
        .filter((i) => variant !== "drawer" || moreItems.includes(i))
        .map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <li key={href}>
              <Link
                href={href}
                onClick={() => setDrawer(false)}
                aria-current={active ? "page" : undefined}
                className={clsx(
                  "flex min-h-11 items-center rounded-full text-sm font-semibold",
                  variant === "rail" ? "flex-col justify-center gap-0.5 rounded-2xl px-1 py-2 text-[10px]" : "gap-3 px-4",
                  active ? "bg-lime text-ink" : admin ? "text-white/85 hover:bg-white/10 hover:text-white" : "text-ink hover:bg-white",
                )}
              >
                <Icon className="size-5 shrink-0" aria-hidden="true" />
                <span className={variant === "rail" ? "text-center leading-tight" : ""}>{label}</span>
              </Link>
            </li>
          );
        })}
    </ul>
  );

  return (
    <div className="min-h-dvh md:flex">
      <aside
        className={clsx(
          "sticky top-0 hidden h-dvh w-24 shrink-0 overflow-y-auto border-r p-2 md:block lg:w-64 lg:p-4",
          admin ? "border-forest bg-forest" : "border-line bg-ground",
        )}
      >
        <div className="mb-4 hidden lg:block">
          <Logo tone={admin ? "light" : "dark"} />
          {admin && (
            <p className="ml-1 mt-1 inline-flex items-center gap-1.5 rounded-full bg-lime px-3 py-1 text-xs font-extrabold uppercase tracking-wide text-forest">
              <ShieldCheck className="size-3.5" aria-hidden="true" />
              Admin console
            </p>
          )}
        </div>
        <nav aria-label={`${title} navigation`} className="lg:hidden">
          {list("rail")}
        </nav>
        <nav aria-label={`${title} navigation`} className="hidden lg:block">
          {list("full")}
        </nav>
      </aside>
      <div className="min-w-0 flex-1">
        <header
          className={clsx(
            "sticky top-0 z-30 flex items-center justify-between border-b px-4 py-2 backdrop-blur md:hidden",
            admin ? "border-forest bg-forest text-white" : "border-line bg-ground/95",
          )}
        >
          <Logo tone={admin ? "light" : "dark"} />
          <button type="button" onClick={() => setDrawer(true)} className="inline-flex min-h-11 items-center gap-2 rounded-full px-3 text-sm font-semibold" aria-label={mobileHrefs ? "More" : "Open menu"}>
            <Menu className="size-5" aria-hidden="true" />
            {mobileHrefs ? "More" : "Menu"}
          </button>
        </header>
        {admin && (
          <div role="note" className="flex items-center gap-2 border-b border-lime/60 bg-lime/30 px-4 py-2 text-xs font-semibold text-forest md:px-6 md:text-sm">
            <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
            Admin console. Every action you take here is recorded with your name, the time and your reason.
          </div>
        )}
        <main id="main" className="mx-auto w-full max-w-6xl px-4 pb-28 pt-4 md:px-6 md:pb-10 md:pt-6">
          {children}
        </main>
      </div>
      <Modal open={drawer} title={mobileHrefs ? "More" : `${title} menu`} onClose={() => setDrawer(false)}>
        <nav aria-label={`${title} menu`}>{list("drawer")}</nav>
      </Modal>
      {mobileHrefs && <BottomNav items={mobileItems} label={`${title} mobile`} />}
    </div>
  );
}
