"use client";
import { Flag } from "lucide-react";
import { useState } from "react";
import { SignInPrompt } from "@/components/auth/SignInPrompt";
import { FormError } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/Button";
import { Select, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import { useMe } from "@/lib/auth";

const reasons = [
  ["scam", "It looks like a scam"],
  ["banned_item", "It is a banned item"],
  ["fake", "Fake or misleading"],
  ["wrong_info", "Wrong price or details"],
  ["abuse", "Abusive or inappropriate"],
  ["other", "Something else"],
] as const;

export function ReportButton({ targetType, targetId, label = "Report", compact = false }: { targetType: "listing" | "user" | "message" | "review"; targetId: string; label?: string; compact?: boolean }) {
  const me = useMe();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState(false);
  const [reason, setReason] = useState("scam");
  const [details, setDetails] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/reports", { method: "POST", body: { target_type: targetType, target_id: targetId, reason, details } });
      toast("Report sent. Our team will review it.");
      setOpen(false);
      setDetails("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send your report.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {compact ? (
        <button type="button" onClick={() => (me.data ? setOpen(true) : setPrompt(true))} disabled={me.isPending} aria-label={`${label} ${targetType}`} className="grid size-11 place-items-center rounded-full text-muted hover:bg-white/60">
          <Flag className="size-3.5" aria-hidden="true" />
        </button>
      ) : (
        <Button variant="tertiary" onClick={() => (me.data ? setOpen(true) : setPrompt(true))} disabled={me.isPending}>
          <Flag className="size-4" aria-hidden="true" />
          {label}
        </Button>
      )}
      <SignInPrompt open={prompt} onClose={() => setPrompt(false)} reason="report this" />
      <Modal open={open} title={`Report this ${targetType}`} onClose={() => setOpen(false)} dirty={details.length > 0}>
        <form onSubmit={submit} className="space-y-3" noValidate>
          <Select label="What is wrong?" value={reason} onChange={(e) => setReason(e.target.value)}>
            {reasons.map(([v, t]) => (
              <option key={v} value={v}>{t}</option>
            ))}
          </Select>
          <Textarea label="Details (optional)" value={details} onChange={(e) => setDetails(e.target.value)} />
          <FormError message={error} />
          <Button type="submit" className="w-full" loading={busy}>Send report</Button>
        </form>
      </Modal>
    </>
  );
}
