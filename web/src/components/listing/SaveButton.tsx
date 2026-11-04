"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart } from "lucide-react";
import { useState } from "react";
import { SignInPrompt } from "@/components/auth/SignInPrompt";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import { useMe } from "@/lib/auth";
import type { ListingCardData } from "@/lib/types";

export function SaveButton({ publicId }: { publicId: string }) {
  const me = useMe();
  const client = useQueryClient();
  const toast = useToast();
  const [prompt, setPrompt] = useState(false);
  const [busy, setBusy] = useState(false);
  const saved = useQuery({ queryKey: ["saved"], queryFn: () => api<ListingCardData[]>("/saved"), enabled: !!me.data });
  const isSaved = !!saved.data?.some((s) => s.public_id === publicId);

  async function toggle() {
    if (!me.data) return setPrompt(true);
    setBusy(true);
    try {
      await api(`/saved/${publicId}`, { method: isSaved ? "DELETE" : "PUT" });
      await client.invalidateQueries({ queryKey: ["saved"] });
      toast(isSaved ? "Removed from saved" : "Saved", "info");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not update saved items", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button variant="tertiary" onClick={toggle} loading={busy} disabled={me.isPending} aria-pressed={isSaved}>
        <Heart className={isSaved ? "size-4 fill-ink" : "size-4"} aria-hidden="true" />
        {isSaved ? "Saved" : "Save"}
      </Button>
      <SignInPrompt open={prompt} onClose={() => setPrompt(false)} reason="save items" />
    </>
  );
}
