"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Bell } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { RequireAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/format";
import { enablePush } from "@/lib/push";

type Page = components["schemas"]["NotificationPage"];

function Notifications() {
  const client = useQueryClient();
  const router = useRouter();
  const toast = useToast();
  const [pushBusy, setPushBusy] = useState(false);
  const list = useQuery({ queryKey: ["notifications"], queryFn: () => api<Page>("/notifications"), refetchInterval: 15000 });

  async function open(n: Page["items"][number]) {
    if (!n.read) {
      await api(`/notifications/${n.id}/read`, { method: "POST" });
      await client.invalidateQueries({ queryKey: ["notifications"] });
    }
    router.push(n.url);
  }

  async function markAll() {
    await api("/notifications/read-all", { method: "POST" });
    await client.invalidateQueries({ queryKey: ["notifications"] });
    toast("All marked as read", "info");
  }

  async function push() {
    setPushBusy(true);
    const result = await enablePush();
    toast(result.message, result.ok ? "success" : "error");
    setPushBusy(false);
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-3xl font-extrabold">Notifications</h1>
        <div className="flex gap-2">
          <Button variant="tertiary" onClick={() => void push()} loading={pushBusy}>Turn on push</Button>
          <Button variant="tertiary" onClick={() => void markAll()} disabled={!list.data?.unread}>Mark all read</Button>
        </div>
      </div>
      {list.isPending && <div role="status" aria-label="Loading" className="space-y-2">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-16" />)}</div>}
      {list.isError && <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />}
      {list.data && !list.data.items.length && <EmptyState title="You are all caught up" body="Messages, orders, payments and request replies show up here." action={{ label: "Browse listings", href: "/search" }} />}
      {list.data && list.data.items.length > 0 && (
        <ul className="space-y-2">
          {list.data.items.map((n) => (
            <li key={n.id}>
              <button type="button" onClick={() => void open(n)} className="block w-full text-left">
                <Card className={clsx("flex min-h-16 items-start gap-3 hover:border-ink", !n.read && "border-ink bg-lime/20")}>
                  <Bell className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold">{n.title}{!n.read && <span className="sr-only"> (unread)</span>}</span>
                    {n.body && <span className="block text-sm text-muted">{n.body}</span>}
                  </span>
                  <span className="shrink-0 text-xs text-muted">{timeAgo(n.created_at)}</span>
                </Card>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function NotificationsPage() {
  return (
    <RequireAuth>
      <Notifications />
    </RequireAuth>
  );
}
