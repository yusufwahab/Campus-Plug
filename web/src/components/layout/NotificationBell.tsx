"use client";
import { useQuery } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { useMe } from "@/lib/auth";

export function NotificationBell() {
  const me = useMe();
  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<components["schemas"]["NotificationPage"]>("/notifications"),
    enabled: !!me.data,
    refetchInterval: 30000,
  });
  const unread = data?.unread ?? 0;
  return (
    <Link href="/notifications" aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"} className="relative grid size-11 place-items-center rounded-full hover:bg-white">
      <Bell className="size-5" aria-hidden="true" />
      {unread > 0 && <span aria-hidden="true" className="absolute right-1 top-1 grid min-w-5 place-items-center rounded-full bg-lime px-1 text-[11px] font-bold">{unread > 9 ? "9+" : unread}</span>}
    </Link>
  );
}
