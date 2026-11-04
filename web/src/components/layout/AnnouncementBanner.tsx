"use client";
import { useQuery } from "@tanstack/react-query";
import { Megaphone, X } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";

type Announcement = components["schemas"]["AnnouncementPublic"];

/** Admin announcements, shown above the page. Dismissal lasts for the browser session. */
export function AnnouncementBanner() {
  const [dismissed, setDismissed] = useState<number[]>(() => (typeof window === "undefined" ? [] : (JSON.parse(window.sessionStorage.getItem("cp_dismissed") ?? "[]") as number[])));
  const { data } = useQuery({ queryKey: ["announcements"], queryFn: () => api<Announcement[]>("/announcements"), staleTime: 120_000 });
  const item = data?.find((a) => !dismissed.includes(a.id));
  if (!item) return null;
  return (
    <div role="region" aria-label="Announcement" className="mb-4 flex items-start gap-3 rounded-card bg-info-bg p-4 text-info-fg">
      <Megaphone className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div className="flex-1">
        <p className="font-bold">{item.title}</p>
        <p className="text-sm">{item.body}</p>
      </div>
      <button
        type="button"
        aria-label="Dismiss announcement"
        className="grid size-11 shrink-0 place-items-center rounded-full hover:bg-white/50"
        onClick={() => {
          const next = [...dismissed, item.id];
          window.sessionStorage.setItem("cp_dismissed", JSON.stringify(next));
          setDismissed(next);
        }}
      >
        <X className="size-5" aria-hidden="true" />
      </button>
    </div>
  );
}
