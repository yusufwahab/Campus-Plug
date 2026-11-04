"use client";
import { useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { API_ORIGIN, api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { useApiQuery } from "@/lib/hooks";

type Detail = components["schemas"]["SubmissionDetail"];
type Decision = "approve" | "reject" | "request_changes";

const copy: Record<Decision, { title: string; body: string; confirm: string; destructive: boolean }> = {
  approve: { title: "Approve this seller?", body: "They get the Verified badge, in-app payments and unlimited listings.", confirm: "Approve", destructive: false },
  reject: { title: "Reject this submission?", body: "The seller sees your reason. They can submit again.", confirm: "Reject", destructive: true },
  request_changes: { title: "Ask for changes?", body: "Tell the seller exactly what to fix. They can resubmit.", confirm: "Request changes", destructive: false },
};

export default function VerifyDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const client = useQueryClient();
  const toast = useToast();
  const detail = useApiQuery<Detail>(["verify", id], `/verify/${id}`);
  const [decision, setDecision] = useState<Decision | null>(null);

  if (detail.isPending) return <Skeleton className="h-64" />;
  if (detail.isError) return <ErrorState message={detail.error.message} onRetry={() => void detail.refetch()} />;
  const d = detail.data;

  return (
    <>
      <PageHeader title={d.shop_name}>
        <Badge tone={d.status === "pending" ? "pending" : d.status === "approved" ? "verified" : "danger"}>{d.status.replace("_", " ")}</Badge>
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-2">
          <h2 className="text-lg font-bold">Seller</h2>
          <p><span className="text-muted">Name: </span>{d.seller_name}</p>
          <p><span className="text-muted">Seller ID: </span>{d.shop_public_id}</p>
          <p><span className="text-muted">Type: </span>{d.kind === "identity" ? "Identity check" : "Payout details review"}</p>
          {d.note && <p><span className="text-muted">Seller note: </span>{d.note}</p>}
          {d.reason && <p className="rounded-input bg-ground p-3 text-sm"><span className="font-semibold">Previous decision: </span>{d.reason}</p>}
          <p className="text-xs text-muted">Viewing a student ID is logged against your account. The link works for five minutes.</p>
        </Card>
        <Card>
          <h2 className="mb-2 text-lg font-bold">Student ID</h2>
          {d.student_id_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- private short-lived link, not optimisable
            <img src={`${API_ORIGIN}${d.student_id_url}`} alt={`Student ID submitted by ${d.seller_name}`} className="max-h-96 w-full rounded-input object-contain" />
          ) : (
            <p className="text-sm text-muted">No ID attached. This is a payout details review for an already verified seller.</p>
          )}
        </Card>
      </div>
      {d.status === "pending" && (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => setDecision("approve")}>Approve</Button>
          <Button variant="tertiary" onClick={() => setDecision("request_changes")}>Request changes</Button>
          <Button variant="danger" onClick={() => setDecision("reject")}>Reject</Button>
        </div>
      )}
      {decision && (
        <ReasonModal
          open
          title={copy[decision].title}
          description={copy[decision].body}
          confirmLabel={copy[decision].confirm}
          destructive={copy[decision].destructive}
          onConfirm={async (reason) => {
            await api(`/verify/${id}/decision`, { method: "POST", body: { decision, reason } });
            await client.invalidateQueries({ queryKey: ["verify-queue"] });
            toast("Decision saved");
            router.push("/verify");
          }}
          onClose={() => setDecision(null)}
        />
      )}
    </>
  );
}
