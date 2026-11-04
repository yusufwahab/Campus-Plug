"use client";
import { Search, ShieldCheck, UserCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { useMe } from "@/lib/auth";
import { publicDesktopLinks, publicMobileNav } from "@/lib/nav";
import { BottomNav } from "./BottomNav";
import { LocationSelector } from "./LocationSelector";
import { NotificationBell } from "./NotificationBell";
import { AnnouncementBanner } from "./AnnouncementBanner";
import { InstallPrompt } from "./InstallPrompt";

function SearchBox({ className }: { className?: string }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  return (
    <form
      role="search"
      className={className}
      onSubmit={(e) => {
        e.preventDefault();
        router.push(q.trim() ? `/search?q=${encodeURIComponent(q.trim())}` : "/search");
      }}
    >
      <label htmlFor="site-search" className="sr-only">
        Search products, services and sellers
      </label>
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden="true" />
        <input
          id="site-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search products, services, sellers or CP-P-48213"
          className="min-h-11 w-full rounded-full border border-line bg-white pl-11 pr-4 text-sm"
        />
      </div>
    </form>
  );
}

export function PublicShell({ children }: { children: ReactNode }) {
  const me = useMe();
  const isAdmin = me.data?.role === "admin" || me.data?.role === "super_admin";
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-ground/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-2 md:px-6">
          <Logo />
          <SearchBox className="hidden flex-1 md:block" />
          <div className="hidden md:block">
            <LocationSelector />
          </div>
          <nav aria-label="Main" className="ml-auto hidden items-center gap-1 md:flex">
            {publicDesktopLinks.map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href} aria-label={label} className="inline-flex min-h-11 items-center gap-2 rounded-full px-3 text-sm font-semibold hover:bg-white">
                <Icon className="size-5 lg:hidden" aria-hidden="true" />
                <span className="hidden lg:inline">{label}</span>
              </Link>
            ))}
            <NotificationBell />
            {isAdmin ? (
              <Button href="/admin">
                <ShieldCheck className="size-4" aria-hidden="true" />
                Admin
              </Button>
            ) : (
              <Button href="/seller/start" variant="secondary">
                Sell
              </Button>
            )}
            <Link href="/account" aria-label="Account" className="grid size-11 place-items-center rounded-full border-2 border-ink">
              <UserCircle className="size-5" aria-hidden="true" />
            </Link>
          </nav>
          <div className="ml-auto flex items-center gap-1 md:hidden">
            <LocationSelector />
          </div>
        </div>
        <div className="px-4 pb-2 md:hidden">
          <SearchBox />
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 pb-28 pt-4 md:px-6 md:pb-10">
        <AnnouncementBanner />
        {children}
      </main>
      <InstallPrompt />
      <BottomNav items={publicMobileNav} label="Mobile" />
    </div>
  );
}
