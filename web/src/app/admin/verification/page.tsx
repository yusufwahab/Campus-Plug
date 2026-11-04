"use client";
import Link from "next/link";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import type { components } from "@/lib/api-schema";
import { useAction, useApiQuery } from "@/lib/hooks";

type Row = components["schemas"]["VerificationRow"];
type Member = components["schemas"]["TeamMember"];

export default function AdminVerification() {
  const [status, setStatus] = useState("pending");
  const rows = useApiQuery<Row[]>(["admin-verification"], "/admin/verification", { status });
  const team = useApiQuery<Member[]>(["admin-team"], "/admin/team");
  const act = useAction([["admin-verification"]]);
  const [assigning, setAssigning] = useState<Row | null>(null);
  const [verifier, setVerifier] = useState("");
  const verifiers = team.data?.filter((m) => m.permissions.includes("verifier") || m.role === "admin" || m.role === "super_admin") ?? [];

  return (
    <>
      <PageHeader title="Verification">
        <div className="w-44">
          <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="pending">Pending</option>
            <option value="changes_requested">Changes requested</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </Select>
        </div>
      </PageHeader>
      <DataTable
        label="Verification submissions"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.id}
        empty={{ title: "Nothing to review", body: "New seller submissions appear here." }}
        columns={[
          { key: "shop", header: "Shop", render: (r) => r.shop_name },
          { key: "id", header: "Seller ID", render: (r) => r.shop_public_id },
          { key: "kind", header: "Type", render: (r) => (r.kind === "identity" ? "Identity" : "Payout review") },
          { key: "status", header: "Status", render: (r) => <Badge tone={r.status === "pending" ? "pending" : r.status === "approved" ? "verified" : "danger"}>{r.status.replace("_", " ")}</Badge> },
          { key: "who", header: "Assigned to", render: (r) => (r.assigned_verifier_id ? `Verifier #${r.assigned_verifier_id}` : "Unassigned") },
        ]}
        actions={(r) =>
          r.status === "pending" ? (
            <>
              <Button variant="tertiary" onClick={() => setAssigning(r)}>Assign</Button>
              <Button variant="secondary" href={`/verify/${r.id}`}>Review</Button>
            </>
          ) : (
            <Link href={`/verify/${r.id}`} className="text-sm font-semibold underline">View</Link>
          )
        }
      />
      <Modal open={!!assigning} title="Assign a Verifier" onClose={() => setAssigning(null)}>
        <Select label="Verifier" value={verifier} onChange={(e) => setVerifier(e.target.value)}>
          <option value="">Choose a Verifier</option>
          {verifiers.map((m) => (
            <option key={m.id} value={m.id}>{m.full_name} ({m.email})</option>
          ))}
        </Select>
        <div className="mt-4 flex justify-end">
          <Button
            disabled={!verifier}
            onClick={async () => {
              if (!assigning) return;
              await act("POST", `/admin/verification/${assigning.id}/assign`, undefined, "Verifier assigned", { verifier_id: Number(verifier) });
              setAssigning(null);
              setVerifier("");
            }}
          >
            Assign
          </Button>
        </div>
      </Modal>
    </>
  );
}
