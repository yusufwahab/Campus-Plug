"use client";
import { useState } from "react";
import { FormError } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { ApiError } from "@/lib/api";

type Props = {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel: string;
  destructive?: boolean;
  /** Extra form controls rendered above the reason (for example a new commission rate). */
  children?: React.ReactNode;
  onConfirm: (reason: string) => Promise<void>;
  onClose: () => void;
};

/** Every Admin action asks for a reason; the API stores who, when, what and why in the activity log. */
export function ReasonModal({ open, title, description, confirmLabel, destructive, children, onConfirm, onClose }: Props) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (reason.trim().length < 3) {
      setError("Give a short reason (at least 3 characters). It is saved in the activity log.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
      setReason("");
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} title={title} onClose={onClose} dirty={reason.length > 0 && !busy}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {description && <p className="text-sm text-muted">{description}</p>}
        {children}
        <Textarea label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} hint="Saved in the activity log with your name and the time." />
        <FormError message={error} />
        <div className="flex flex-col-reverse gap-2 md:flex-row md:justify-end">
          <Button variant="tertiary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant={destructive ? "danger" : "secondary"} loading={busy}>
            {confirmLabel}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
