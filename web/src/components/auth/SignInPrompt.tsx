"use client";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";

/** Shown to guests who try to chat, order, save, report, post a request or sell. */
export function SignInPrompt({ open, onClose, reason = "continue" }: { open: boolean; onClose: () => void; reason?: string }) {
  const next = encodeURIComponent(usePathname());
  return (
    <Modal open={open} title="Sign in to continue" onClose={onClose}>
      <p className="text-sm text-muted">Create a free account or sign in to {reason}.</p>
      <div className="mt-5 flex flex-col gap-2 md:flex-row-reverse">
        <Button href={`/login?next=${next}`}>Sign in</Button>
        <Button href={`/signup?next=${next}`} variant="tertiary">
          Create account
        </Button>
      </div>
    </Modal>
  );
}
