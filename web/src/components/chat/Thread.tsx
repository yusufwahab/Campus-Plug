"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, Check, CheckCheck, ImagePlus, Send } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { FormError } from "@/components/auth/AuthCard";
import { ReportButton } from "@/components/listing/ReportButton";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmModal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api, assetUrl } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { naira } from "@/lib/format";
import { compressImage } from "@/lib/image";
import type { Conversation } from "./ChatShell";
import { OfflineDealModal } from "./OfflineDealModal";
import { PaymentRequestModal } from "./PaymentRequestModal";
import { PaymentRequestCard } from "./PaymentRequestCard";

export type Message = components["schemas"]["MessageOut"];

/** Chat thread. Live updates come from polling every few seconds while the tab is visible */
export function Thread({ id }: { id: number }) {
  const client = useQueryClient();
  const toast = useToast();
  const convo = useQuery({ queryKey: ["conversation", id], queryFn: () => api<Conversation>(`/conversations/${id}`), refetchInterval: 8000 });
  const messages = useQuery({
    queryKey: ["messages", id],
    queryFn: () => api<Message[]>(`/conversations/${id}/messages`),
    refetchInterval: () => (typeof document !== "undefined" && document.hidden ? false : 3000),
  });
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requestOpen, setRequestOpen] = useState(false);
  const [confirmBlock, setConfirmBlock] = useState(false);
  const [offlineOpen, setOfflineOpen] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const count = messages.data?.length ?? 0;

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
    void client.invalidateQueries({ queryKey: ["conversations"] });
  }, [count, client]);

  async function refresh() {
    await Promise.all([client.invalidateQueries({ queryKey: ["messages", id] }), client.invalidateQueries({ queryKey: ["conversation", id] })]);
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    setError(null);
    try {
      await api(`/conversations/${id}/messages`, { method: "POST", body: { body } });
      setText("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Message not sent. Check your connection.");
    } finally {
      setSending(false);
    }
  }

  async function sendImage(file: File | undefined) {
    if (!file) return;
    setSending(true);
    setError(null);
    try {
      const data = new FormData();
      data.append("file", await compressImage(file));
      await api(`/conversations/${id}/images`, { method: "POST", body: data });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Could not send the photo.");
    } finally {
      setSending(false);
    }
  }

  async function act(path: string, body: unknown, done: string) {
    try {
      await api(path, { method: "POST", body });
      await refresh();
      toast(done, "info");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Something went wrong", "error");
    }
  }

  if (convo.isPending) return <Skeleton className="h-96" />;
  if (convo.isError) return <ErrorState message={convo.error.message} onRetry={() => void convo.refetch()} />;
  const c = convo.data;

  return (
    <div className="flex h-[calc(100dvh-14rem)] min-h-96 flex-col rounded-card border border-line bg-white md:h-[70dvh]">
      <header className="flex items-center gap-2 border-b border-line p-3">
        <Link href="/messages" aria-label="Back to conversations" className="grid size-11 place-items-center rounded-full hover:bg-ground md:hidden">
          <ArrowLeft className="size-5" aria-hidden="true" />
        </Link>
        <div className="min-w-0 flex-1">
          <h2 className="truncate font-heading text-lg font-bold">{c.other_name}</h2>
          {c.listing && (
            <Link href={`/listing/${c.listing.public_id}`} className="block truncate text-xs text-muted underline">
              {c.listing.title} · {naira(c.listing.price_kobo)}
            </Link>
          )}
        </div>
        {c.phone && <Badge tone="verified">{c.phone}</Badge>}
      </header>

      <div className="flex flex-wrap gap-2 border-b border-line p-2 text-sm">
        <Button variant="tertiary" className="min-h-11" onClick={() => void act(`/conversations/${id}/share-phone`, { share: !c.i_share_phone }, c.i_share_phone ? "Phone sharing off" : c.they_share_phone ? "Numbers are now visible" : "We will show numbers once they agree too")}>
          {c.i_share_phone ? "Stop sharing my number" : "Share my number"}
        </Button>
        {c.i_am_seller && (
          <Button variant="secondary" onClick={() => setRequestOpen(true)}>
            Request payment
          </Button>
        )}
        {c.listing && (
          <Button variant="tertiary" onClick={() => setOfflineOpen(true)}>
            Record cash deal
          </Button>
        )}
        <Button variant="tertiary" onClick={() => (c.blocked ? void act(`/conversations/${id}/block`, { blocked: false }, "Unblocked") : setConfirmBlock(true))}>
          {c.blocked ? "Unblock" : "Block"}
        </Button>
        <ReportButton targetType="user" targetId={String(c.other_user_id)} label="Report person" />
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3" role="log" aria-label="Messages" aria-live="polite">
        {messages.isPending && <Skeleton className="h-16" />}
        {messages.isError && <ErrorState message="Could not load messages." onRetry={() => void messages.refetch()} />}
        {messages.data && !messages.data.length && <p className="py-8 text-center text-sm text-muted">Say hello and ask about the item.</p>}
        {messages.data?.map((m) => (
          <div key={m.id} className={clsx("flex", m.mine ? "justify-end" : "justify-start")}>
            <div className={clsx("max-w-[85%] rounded-2xl px-4 py-2 text-sm", m.mine ? "bg-lime text-ink" : "bg-ground text-ink")}>
              {m.kind === "image" && m.image_url && <Image src={assetUrl(m.image_url)!} alt="Photo sent in chat" width={240} height={240} unoptimized className="mb-1 h-auto max-h-60 w-auto rounded-xl" />}
              {m.kind === "payment_request" ? <PaymentRequestCard message={m} /> : m.body && <p className="whitespace-pre-wrap break-words">{m.body}</p>}
              <p className="mt-1 flex items-center justify-end gap-1 text-[11px] text-muted">
                {!m.mine && <ReportButton targetType="message" targetId={String(m.id)} label="Report" compact />}
                {new Date(m.created_at).toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit" })}
                {m.mine && (m.read ? <CheckCheck className="size-3.5" aria-label="Read" /> : <Check className="size-3.5" aria-label="Sent" />)}
              </p>
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <form onSubmit={send} className="border-t border-line p-3" noValidate>
        <FormError message={error} />
        <div className="mt-1 flex items-end gap-2">
          <label className="grid size-11 shrink-0 cursor-pointer place-items-center rounded-full border border-line hover:bg-ground focus-within:outline focus-within:outline-2">
            <ImagePlus className="size-5" aria-hidden="true" />
            <span className="sr-only">Send a photo</span>
            <input type="file" accept="image/*" className="sr-only" onChange={(e) => { void sendImage(e.target.files?.[0]); e.target.value = ""; }} />
          </label>
          <div className="flex-1">
            <label htmlFor="chat-input" className="sr-only">Write a message</label>
            <textarea id="chat-input" value={text} rows={1} disabled={c.blocked} placeholder={c.blocked ? "You blocked this person" : "Write a message"} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(e as unknown as React.FormEvent); } }} className="max-h-32 min-h-11 w-full resize-none rounded-input border border-line px-4 py-2.5 text-base" />
          </div>
          <Button type="submit" loading={sending} disabled={!text.trim() || c.blocked} aria-label="Send message">
            <Send className="size-4" aria-hidden="true" />
            <span className="hidden md:inline">Send</span>
          </Button>
        </div>
      </form>

      <PaymentRequestModal open={requestOpen} conversationId={id} defaultPriceKobo={c.listing?.price_kobo ?? 0} onClose={() => setRequestOpen(false)} onSent={refresh} />
      <OfflineDealModal open={offlineOpen} conversationId={id} defaultPriceKobo={c.listing?.price_kobo ?? 0} iAmSeller={c.i_am_seller} onClose={() => setOfflineOpen(false)} />
      <ConfirmModal open={confirmBlock} title={`Block ${c.other_name}?`} body="Neither of you can send messages in this chat until you unblock them." confirmLabel="Block" destructive onConfirm={() => { setConfirmBlock(false); void act(`/conversations/${id}/block`, { blocked: true }, "Blocked"); }} onClose={() => setConfirmBlock(false)} />
    </div>
  );
}
