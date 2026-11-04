"use client";
import { MessageCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { SignInPrompt } from "@/components/auth/SignInPrompt";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import { useMe } from "@/lib/auth";

/** Opens (or reuses) the chat with the seller. Guests are asked to sign in first. */
export function MessageButton({ listingId, className, ownListing }: { listingId: string; className?: string; ownListing?: boolean }) {
  const me = useMe();
  const router = useRouter();
  const toast = useToast();
  const [prompt, setPrompt] = useState(false);
  const [busy, setBusy] = useState(false);

  async function open() {
    if (!me.data) return setPrompt(true);
    setBusy(true);
    try {
      const convo = await api<{ id: number }>("/conversations", { method: "POST", body: { listing_id: listingId } });
      router.push(`/messages/${convo.id}`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not open the chat", "error");
      setBusy(false);
    }
  }

  if (ownListing) return null;
  return (
    <>
      <Button className={className} onClick={open} loading={busy} disabled={me.isPending}>
        <MessageCircle className="size-4" aria-hidden="true" />
        Message seller
      </Button>
      <SignInPrompt open={prompt} onClose={() => setPrompt(false)} reason="message the seller" />
    </>
  );
}
