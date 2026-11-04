"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { FormError } from "@/components/auth/AuthCard";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ApiError, api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { compressImage } from "@/lib/image";

type Submission = components["schemas"]["SubmissionOut"];
type Overview = components["schemas"]["SellerOverview"];

export default function SellerVerification() {
  const client = useQueryClient();
  const toast = useToast();
  const latest = useQuery({ queryKey: ["my-verification"], queryFn: () => api<Submission | null>("/seller/verification") });
  const overview = useQuery({ queryKey: ["seller-overview"], queryFn: () => api<Overview>("/seller/overview") });
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (latest.isPending || overview.isPending) return <Skeleton className="h-48" />;
  if (latest.isError || overview.isError) return <ErrorState message="Could not load your verification." onRetry={() => { void latest.refetch(); void overview.refetch(); }} />;

  const verified = overview.data.shop.verification_status === "verified";
  const pending = latest.data?.status === "pending";
  const payoutReview = verified && overview.data.payout_review_required;
  const canSubmit = !pending && (!verified || payoutReview);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!verified && !file) return setError("Add a clear photo of your student ID.");
    setBusy(true);
    try {
      const data = new FormData();
      if (file) data.append("student_id", await compressImage(file));
      data.append("note", note);
      await api("/seller/verification", { method: "POST", body: data });
      await Promise.all([client.invalidateQueries({ queryKey: ["my-verification"] }), client.invalidateQueries({ queryKey: ["seller-overview"] })]);
      setFile(null);
      setNote("");
      toast("Submitted. A Verifier will review it.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-extrabold md:text-3xl">Verification</h1>
      <Card className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={verified ? "verified" : "pending"}>{verified ? "Verified student" : "Not verified"}</Badge>
          <Badge tone="info">{overview.data.shop.trust_level.replace(/_/g, " ")}</Badge>
        </div>
        <p className="text-sm text-muted">
          {verified ? "You can receive in-app payments and list without a limit." : "Verify to unlock the badge, in-app payments and unlimited listings. Unverified sellers cannot receive in-app payments."}
        </p>
        {latest.data && (
          <p className="rounded-input bg-ground p-3 text-sm">
            <span className="font-semibold">Latest submission: {latest.data.status.replace("_", " ")}.</span> {latest.data.reason && `Reviewer said: ${latest.data.reason}`}
          </p>
        )}
        {payoutReview && <p className="rounded-input bg-pending-bg p-3 text-sm text-pending-fg">You changed your payout details. They need a quick review before your next payout.</p>}
      </Card>

      {pending && <p role="status" className="rounded-card bg-info-bg p-4 text-sm font-semibold text-info-fg">Your submission is waiting for review.</p>}

      {canSubmit && (
        <Card>
          <h2 className="text-lg font-bold">{verified ? "Request a payout details review" : "Submit your student ID"}</h2>
          <form onSubmit={submit} className="mt-3 space-y-3" noValidate>
            {!verified && (
              <div>
                <label htmlFor="student-id" className="text-sm font-semibold">Photo of your student ID</label>
                <input id="student-id" type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="mt-1 block w-full min-h-11 rounded-input border border-line bg-white p-2 text-sm" />
                <p className="mt-1 text-xs text-muted">Stored privately. Only assigned reviewers can open it, through short-lived links, and every view is logged.</p>
              </div>
            )}
            <Textarea label="Note for the reviewer (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
            <FormError message={error} />
            <Button type="submit" loading={busy}>Submit for review</Button>
          </form>
        </Card>
      )}
    </div>
  );
}
