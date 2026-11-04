"use client";
import { Check, Copy, Share2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";

/** Share dialog: copy link, WhatsApp, or the phone's native share sheet when available. */
export function ShareButton({ path, title, label = "Share", onShared }: { path: string; title: string; label?: string; onShared?: () => void }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const toast = useToast();
  const url = typeof window === "undefined" ? path : `${window.location.origin}${path}`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast("Link copied");
      onShared?.();
    } catch {
      toast("Could not copy. Select the link and copy it manually.", "error");
    }
  }

  return (
    <>
      <Button variant="tertiary" onClick={() => setOpen(true)}>
        <Share2 className="size-4" aria-hidden="true" />
        {label}
      </Button>
      <Modal open={open} title="Share" onClose={() => { setOpen(false); setCopied(false); }}>
        <p className="mb-3 break-all rounded-input bg-ground p-3 text-sm" data-testid="share-url">
          {url}
        </p>
        <div className="flex flex-col gap-2">
          <Button onClick={copy}>
            {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
            {copied ? "Copied" : "Copy link"}
          </Button>
          <Button variant="secondary" href={`https://wa.me/?text=${encodeURIComponent(`${title} ${url}`)}`}>
            Share on WhatsApp
          </Button>
          {typeof navigator !== "undefined" && "share" in navigator && (
            <Button variant="tertiary" onClick={() => void navigator.share({ title, url }).then(onShared)}>
              More options
            </Button>
          )}
        </div>
      </Modal>
    </>
  );
}
