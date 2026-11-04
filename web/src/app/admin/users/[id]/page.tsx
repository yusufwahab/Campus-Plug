"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import type { components } from "@/lib/api-schema";
import { useAction, useApiQuery } from "@/lib/hooks";
import { UserButtons, runUserAction, userActionCopy } from "@/components/admin/UserActions";
import type { UserAction } from "@/components/admin/UserActions";

type User = components["schemas"]["UserOut"];

export default function AdminUserDetail() {
  const { id } = useParams<{ id: string }>();
  const user = useApiQuery<User>(["admin-user", id], `/admin/users/${id}`);
  const [action, setAction] = useState<UserAction | null>(null);
  const act = useAction([["admin-user"], ["admin-users"]]);
  const copy = action ? userActionCopy(action) : null;

  if (user.isPending) return <Skeleton className="h-48" />;
  if (user.isError) return <ErrorState message={user.error.message} onRetry={() => void user.refetch()} />;
  const u = user.data;
  const facts: [string, string][] = [
    ["Email", u.email],
    ["Phone", u.phone ?? "Not added"],
    ["Role", u.role],
    ["Add-on permissions", u.permissions.join(", ") || "none"],
    ["Onboarding", u.onboarded ? "Complete" : "Not finished"],
    ["Two-step sign-in", u.mfa_enabled ? "On" : "Off"],
  ];
  return (
    <>
      <PageHeader title={u.full_name}>
        <Badge tone={u.status === "active" ? "verified" : "danger"}>{u.status}</Badge>
        <Badge tone={u.phone_verified ? "verified" : "pending"}>{u.phone_verified ? "Phone confirmed" : "Phone not confirmed"}</Badge>
      </PageHeader>
      <Card>
        <dl className="grid gap-3 md:grid-cols-2">
          {facts.map(([k, v]) => (
            <div key={k}>
              <dt className="text-sm text-muted">{k}</dt>
              <dd className="font-semibold">{v}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-5 flex flex-wrap gap-2">
          <UserButtons user={u} onAction={setAction} />
        </div>
      </Card>
      {copy && action && (
        <ReasonModal open title={copy.title} description={copy.description} confirmLabel={copy.confirm} destructive={copy.destructive} onConfirm={(reason) => runUserAction(act, action, reason)} onClose={() => setAction(null)} />
      )}
    </>
  );
}
