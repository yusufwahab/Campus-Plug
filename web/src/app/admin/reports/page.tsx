"use client";
import Link from "next/link";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { useAction, useApiQuery } from "@/lib/hooks";

type Row = components["schemas"]["ReportRow"];
type Chat = components["schemas"]["AdminChat"];
type ActionName = "hide" | "warn" | "suspend" | "ban" | "dismiss";

const descriptions: Record<ActionName, string> = {
  hide: "Hide the reported content. Listings are removed from the marketplace.",
  warn: "Send a recorded warning to the account that owns the content.",
  suspend: "Suspend the owner's account. They are signed out immediately.",
  ban: "Ban the owner's account permanently.",
  dismiss: "Close the report without action.",
};

export default function AdminReports() {
  const [status, setStatus] = useState("open");
  const rows = useApiQuery<Row[]>(["admin-reports"], "/admin/reports", { status });
  const act = useAction([["admin-reports"], ["admin-overview"]]);
  const [target, setTarget] = useState<Row | null>(null);
  const [action, setAction] = useState<ActionName>("warn");
  const [viewing, setViewing] = useState<Row | null>(null);
  const [chat, setChat] = useState<Chat | null>(null);

  return (
    <>
      <PageHeader title="Reports">
        <div className="w-44">
          <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="open">Open</option>
            <option value="actioned">Actioned</option>
            <option value="dismissed">Dismissed</option>
          </Select>
        </div>
      </PageHeader>
      <DataTable
        label="Reports"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.id}
        empty={{ title: "No reports", body: "Reports from users appear here for review." }}
        columns={[
          { key: "t", header: "Target", render: (r) => (r.target_type === "listing" ? <Link className="font-semibold underline" href={`/listing/${r.target_id}`}>{r.target_id}</Link> : `${r.target_type} ${r.target_id}`) },
          { key: "reason", header: "Reason", render: (r) => r.reason.replace("_", " ") },
          { key: "d", header: "Details", render: (r) => r.details || "None" },
          { key: "s", header: "Status", render: (r) => <Badge tone={r.status === "open" ? "pending" : "neutral"}>{r.status}</Badge> },
          { key: "res", header: "Resolution", render: (r) => r.resolution || "None" },
        ]}
        actions={(r) => (
          <>
            {r.conversation_id && <Button variant="tertiary" onClick={() => { setChat(null); setViewing(r); }}>View chat</Button>}
            {r.status === "open" && <Button variant="secondary" onClick={() => { setTarget(r); setAction("warn"); }}>Review</Button>}
          </>
        )}
      />
      {viewing && (
        <ReasonModal
          open
          title="Open this private chat?"
          description="Private chats can be opened only because a message in them was reported. Your name, the time and your reason are logged."
          confirmLabel="Open chat"
          onConfirm={async (reason) => {
            setChat(await api<Chat>(`/admin/conversations/${viewing.conversation_id}`, { query: { reason } }));
          }}
          onClose={() => setViewing(null)}
        />
      )}
      <Modal open={!!chat} title={chat ? `Chat between ${chat.participants.join(" and ")}` : "Chat"} onClose={() => { setChat(null); setViewing(null); }}>
        <ul className="max-h-[50dvh] space-y-2 overflow-y-auto">
          {chat?.messages.map((m) => (
            <li key={m.id} className="rounded-input bg-ground p-3 text-sm">
              <p className="text-xs text-muted">{new Date(m.created_at).toLocaleString("en-NG")}</p>
              <p>{m.kind === "image" ? "[Photo]" : m.kind === "payment_request" ? "[Payment request]" : m.body}</p>
            </li>
          ))}
        </ul>
      </Modal>
      {target && (
        <ReasonModal
          open
          title={`Review report #${target.id}`}
          description={descriptions[action]}
          confirmLabel={action === "dismiss" ? "Dismiss report" : "Apply action"}
          destructive={action === "ban" || action === "suspend" || action === "hide"}
          onConfirm={(reason) => act("POST", `/admin/reports/${target.id}/resolve`, { action, reason }, "Report resolved").then(() => undefined)}
          onClose={() => setTarget(null)}
        >
          <Select label="Action" value={action} onChange={(e) => setAction(e.target.value as ActionName)}>
            <option value="warn">Warn the owner</option>
            <option value="hide">Hide the content</option>
            <option value="suspend">Suspend the owner</option>
            <option value="ban">Ban the owner</option>
            <option value="dismiss">Dismiss</option>
          </Select>
        </ReasonModal>
      )}
    </>
  );
}
