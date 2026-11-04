"use client";
import Link from "next/link";
import { useState } from "react";
import { PageHeader, SearchBar } from "@/components/admin/PageHeader";
import { DataTable } from "@/components/admin/DataTable";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { UserButtons, runUserAction, userActionCopy } from "@/components/admin/UserActions";
import type { UserAction } from "@/components/admin/UserActions";
import { Badge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Field";
import type { components } from "@/lib/api-schema";
import { useAction, useApiQuery, useDebounced } from "@/lib/hooks";

type Page = { items: components["schemas"]["UserOut"][]; total: number };
export default function AdminUsers() {
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(1);
  const search = useDebounced(q);
  const users = useApiQuery<Page>(["admin-users"], "/admin/users", { q: search, role, page });
  const [action, setAction] = useState<UserAction | null>(null);
  const act = useAction([["admin-users"]]);
  const copy = action ? userActionCopy(action) : null;

  return (
    <>
      <PageHeader title="Users" />
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 basis-56"><SearchBar value={q} onChange={(v) => { setQ(v); setPage(1); }} label="Search name, email or phone" /></div>
        <div className="w-full md:w-44">
          <Select label="Role" value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }}>
            <option value="">All roles</option>
            <option value="buyer">Buyers</option>
            <option value="seller">Sellers</option>
            <option value="admin">Admins</option>
          </Select>
        </div>
      </div>
      <DataTable
        label="Users"
        rows={users.data?.items}
        loading={users.isPending}
        error={users.isError ? users.error.message : null}
        onRetry={() => void users.refetch()}
        rowKey={(u) => u.id}
        page={page}
        total={users.data?.total}
        onPage={setPage}
        empty={{ title: "No users match", body: "Try a different search or role." }}
        columns={[
          { key: "name", header: "Name", render: (u) => <Link className="font-semibold underline" href={`/admin/users/${u.id}`}>{u.full_name}</Link> },
          { key: "email", header: "Email", render: (u) => u.email },
          { key: "role", header: "Role", render: (u) => <Badge tone="neutral">{u.role}</Badge> },
          { key: "perms", header: "Add-ons", render: (u) => (u.permissions.length ? u.permissions.join(", ") : "none") },
          { key: "status", header: "Status", render: (u) => <Badge tone={u.status === "active" ? "verified" : "danger"}>{u.status}</Badge> },
        ]}
        actions={(u) => <UserButtons user={u} onAction={setAction} />}
      />
      {copy && action && (
        <ReasonModal open title={copy.title} description={copy.description} confirmLabel={copy.confirm} destructive={copy.destructive} onConfirm={(reason) => runUserAction(act, action, reason)} onClose={() => setAction(null)} />
      )}
    </>
  );
}
