"use client";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { UserButtons, runUserAction, userActionCopy } from "@/components/admin/UserActions";
import type { UserAction } from "@/components/admin/UserActions";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import type { components } from "@/lib/api-schema";
import { useAction, useApiQuery } from "@/lib/hooks";
import { api } from "@/lib/api";

type Member = components["schemas"]["TeamMember"];
type User = components["schemas"]["UserOut"];

export default function AdminTeam() {
  const team = useApiQuery<Member[]>(["admin-team"], "/admin/team");
  const act = useAction([["admin-team"], ["admin-users"]]);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [action, setAction] = useState<UserAction | null>(null);
  const [lookup, setLookup] = useState("");
  const [lookupError, setLookupError] = useState<string | null>(null);
  const copy = action ? userActionCopy(action) : null;

  async function findUser() {
    setLookupError(null);
    const res = await api<{ items: User[] }>("/admin/users", { query: { q: lookup.trim() } });
    const found = res.items.find((u) => u.email.toLowerCase() === lookup.trim().toLowerCase());
    if (!found) return setLookupError("No account with that email.");
    setAction({ user: found, kind: "verifier" });
  }

  return (
    <>
      <PageHeader title="Team">
        <Button onClick={() => setInviteOpen(true)}>Add an Admin</Button>
      </PageHeader>
      <p className="mb-4 text-sm text-muted">Admins have full access and must use two-step sign-in. Verifiers and Hall Reps are limited add-ons on normal accounts.</p>
      <DataTable
        label="Team"
        rows={team.data}
        loading={team.isPending}
        error={team.isError ? team.error.message : null}
        onRetry={() => void team.refetch()}
        rowKey={(m) => m.id}
        columns={[
          { key: "n", header: "Name", render: (m) => m.full_name },
          { key: "e", header: "Email", render: (m) => m.email },
          { key: "r", header: "Role", render: (m) => <Badge tone={m.role === "buyer" || m.role === "seller" ? "neutral" : "info"}>{m.role}</Badge> },
          { key: "p", header: "Add-ons", render: (m) => (m.permissions.length ? m.permissions.map((p) => p.replace("_", " ")).join(", ") : "none") },
        ]}
        actions={(m) =>
          m.role === "buyer" || m.role === "seller" ? (
            <UserButtons user={{ id: m.id, email: m.email, full_name: m.full_name, role: m.role, permissions: m.permissions, status: "active", phone: null, phone_verified: true, campus_id: null, location_id: null, interests: [], onboarded: true, mfa_enabled: false, notify_optional: true }} onAction={setAction} />
          ) : null
        }
      />

      <section className="mt-8 max-w-md space-y-2">
        <h2 className="text-lg font-bold">Give someone an add-on permission</h2>
        <Input label="Their account email" value={lookup} onChange={(e) => setLookup(e.target.value)} error={lookupError ?? undefined} />
        <Button variant="secondary" onClick={() => void findUser()} disabled={!lookup.includes("@")}>Find account</Button>
      </section>

      <ReasonModal
        open={inviteOpen}
        title="Add an Admin"
        description="They must already have an account. They enrol two-step sign-in the next time they sign in."
        confirmLabel="Make Admin"
        onConfirm={(reason) => act("POST", "/admin/team/admins", { email, reason }, "Admin added").then(() => setEmail(""))}
        onClose={() => setInviteOpen(false)}
      >
        <Input label="Account email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </ReasonModal>
      {copy && action && (
        <ReasonModal open title={copy.title} description={copy.description} confirmLabel={copy.confirm} destructive={copy.destructive} onConfirm={(reason) => runUserAction(act, action, reason)} onClose={() => setAction(null)} />
      )}
    </>
  );
}
