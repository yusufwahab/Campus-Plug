"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { SignInPrompt } from "@/components/auth/SignInPrompt";
import { FormError } from "@/components/auth/AuthCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Field";
import { ConfirmModal, Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { useMe } from "@/lib/auth";
import { naira, timeAgo } from "@/lib/format";

type Req = components["schemas"]["RequestOut"];

export default function RequestDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const client = useQueryClient();
  const toast = useToast();
  const me = useMe();
  const req = useQuery({ queryKey: ["request", id], queryFn: () => api<Req>(`/requests/${id}`) });
  const [reply, setReply] = useState("");
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (req.isPending) return <Skeleton className="h-48" />;
  if (req.isError) return <ErrorState message={req.error.message} onRetry={() => void req.refetch()} />;
  const r = req.data;
  const isSeller = me.data?.role === "seller";

  async function respond(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const chat = await api<{ id: number }>(`/requests/${id}/respond`, { method: "POST", body: { message: reply } });
      toast("Reply sent");
      router.push(`/messages/${chat.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send your reply.");
      setBusy(false);
    }
  }

  async function close() {
    await api(`/requests/${id}/close`, { method: "POST" });
    await client.invalidateQueries({ queryKey: ["request", id] });
    await client.invalidateQueries({ queryKey: ["requests"] });
    setConfirmClose(false);
    toast("Request closed", "info");
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Card className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={r.status === "open" ? "verified" : "neutral"}>{r.status}</Badge>
          {r.category_name && <Badge tone="neutral">{r.category_name}</Badge>}
          {r.budget_kobo && <Badge tone="info">Budget {naira(r.budget_kobo)}</Badge>}
        </div>
        <h1 className="text-2xl font-extrabold">{r.title}</h1>
        {r.description && <p className="whitespace-pre-line">{r.description}</p>}
        <p className="text-sm text-muted">
          {r.buyer_first_name} · {r.location_name ?? "Anywhere on campus"} · posted {timeAgo(r.created_at)} · {r.responses} {r.responses === 1 ? "reply" : "replies"}
          {r.deadline && ` · needed by ${new Date(r.deadline).toLocaleDateString("en-NG")}`}
        </p>
        {r.status === "open" && !r.mine && (
          r.i_responded ? <Badge tone="info">You replied. Check Messages.</Badge> : (
            <Button onClick={() => (me.data ? (isSeller ? setOpen(true) : router.push("/seller/start")) : setPrompt(true))}>
              {me.data && !isSeller ? "Open a shop to reply" : "I can help"}
            </Button>
          )
        )}
        {r.mine && r.status === "open" && <Button variant="tertiary" onClick={() => setConfirmClose(true)}>Close request</Button>}
      </Card>
      <SignInPrompt open={prompt} onClose={() => setPrompt(false)} reason="reply to this request" />
      <ConfirmModal open={confirmClose} title="Close this request?" body="Sellers will no longer see it. You can post it again later." confirmLabel="Close request" onConfirm={() => void close()} onClose={() => setConfirmClose(false)} />
      <Modal open={open} title="Reply to this request" onClose={() => setOpen(false)} dirty={reply.length > 0}>
        <form onSubmit={respond} className="space-y-3" noValidate>
          <Textarea label="Your message" hint="Say what you can offer and your price. This opens a chat." value={reply} onChange={(e) => setReply(e.target.value)} />
          <FormError message={error} />
          <Button type="submit" className="w-full" loading={busy} disabled={reply.trim().length < 2}>Send reply</Button>
        </form>
      </Modal>
    </div>
  );
}
