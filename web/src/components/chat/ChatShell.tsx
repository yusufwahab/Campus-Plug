"use client";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import Link from "next/link";
import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { timeAgo } from "@/lib/format";

export type Conversation = components["schemas"]["ConversationOut"];

/**
 * Mobile: either the list or the thread, one screen at a time.
 * Tablet and desktop: list on the left, thread on the right.
 */
export function ChatShell({ activeId, basePath, children }: { activeId?: number; basePath: string; children?: ReactNode }) {
  const list = useQuery({ queryKey: ["conversations"], queryFn: () => api<Conversation[]>("/conversations"), refetchInterval: 5000 });
  return (
    <div className="grid min-h-[70dvh] gap-4 md:grid-cols-[320px_minmax(0,1fr)]">
      <aside className={clsx(activeId ? "hidden md:block" : "block")} aria-label="Conversations">
        <h1 className="mb-3 text-3xl font-extrabold">Messages</h1>
        {list.isPending && (
          <div role="status" aria-label="Loading" className="space-y-2">
            {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-16" />)}
          </div>
        )}
        {list.isError && <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />}
        {list.data && !list.data.length && <EmptyState title="No conversations yet" body="Message a seller from any listing to start chatting." action={{ label: "Browse listings", href: "/search" }} />}
        {list.data && list.data.length > 0 && (
          <ul className="space-y-2">
            {list.data.map((c) => (
              <li key={c.id}>
                <Link
                  href={`${basePath}/${c.id}`}
                  aria-current={c.id === activeId ? "page" : undefined}
                  className={clsx("flex min-h-16 items-center gap-3 rounded-card border p-3", c.id === activeId ? "border-ink bg-white" : "border-line bg-white hover:border-ink")}
                >
                  <span aria-hidden="true" className="grid size-11 shrink-0 place-items-center rounded-full bg-lilac font-heading text-lg font-bold">
                    {c.other_name.charAt(0).toUpperCase()}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate font-semibold">{c.other_name}</span>
                      <span className="shrink-0 text-xs text-muted">{timeAgo(c.last_message_at)}</span>
                    </span>
                    <span className="block truncate text-xs text-muted">{c.listing?.title}</span>
                    <span className="block truncate text-sm">{c.last_message || "No messages yet"}</span>
                  </span>
                  {c.unread > 0 && (
                    <span className="grid min-w-6 place-items-center rounded-full bg-lime px-1.5 text-xs font-bold" aria-label={`${c.unread} unread`}>
                      {c.unread}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </aside>
      <section className={clsx(activeId ? "block" : "hidden md:block")} aria-label="Conversation">
        {children ?? (
          <div className="hidden h-full place-items-center rounded-card border border-dashed border-line bg-white p-8 text-center md:grid">
            <p className="text-muted">Choose a conversation to read and reply.</p>
          </div>
        )}
      </section>
    </div>
  );
}
