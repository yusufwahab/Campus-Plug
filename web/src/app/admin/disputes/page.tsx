"use client";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DataTable } from "@/components/admin/DataTable";
import { PageHeader } from "@/components/admin/PageHeader";
import { ReasonModal } from "@/components/admin/ReasonModal";
import { BuyerBreakdown, Timeline } from "@/components/orders/parts";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { naira, nairaToKobo } from "@/lib/format";
import { useAction, useApiQuery } from "@/lib/hooks";

type Row = components["schemas"]["DisputeRow"];
type Detail = components["schemas"]["DisputeDetail"];
type Decision = "full_refund" | "partial_refund" | "release";

export default function AdminDisputes() {
  const [status, setStatus] = useState("");
  const rows = useApiQuery<Row[]>(["admin-disputes"], "/admin/disputes", { status });
  const act = useAction([["admin-disputes"], ["admin-orders"]]);
  const [open, setOpen] = useState<string | null>(null);
  const [deciding, setDeciding] = useState<Row | null>(null);
  const [decision, setDecision] = useState<Decision>("release");
  const [partial, setPartial] = useState("");
  const detail = useQuery({ queryKey: ["admin-dispute", open], queryFn: () => api<Detail>(`/admin/disputes/${open}`), enabled: !!open });
  const [chat, setChat] = useState<components["schemas"]["AdminChat"] | null>(null);
  const [viewChat, setViewChat] = useState<number | null>(null);

  const d = detail.data?.order.dispute;
  return (
    <>
      <PageHeader title="Disputes">
        <div className="w-44">
          <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="awaiting_seller">Awaiting seller</option>
            <option value="under_review">Under review</option>
            <option value="resolved">Resolved</option>
          </Select>
        </div>
      </PageHeader>
      <DataTable
        label="Disputes"
        rows={rows.data}
        loading={rows.isPending}
        error={rows.isError ? rows.error.message : null}
        onRetry={() => void rows.refetch()}
        rowKey={(r) => r.public_id}
        empty={{ title: "No disputes", body: "When a buyer reports a problem it appears here." }}
        columns={[
          { key: "id", header: "Dispute", render: (r) => r.public_id },
          { key: "o", header: "Order", render: (r) => r.order_id },
          { key: "r", header: "Reason", render: (r) => r.reason.replace(/_/g, " ") },
          { key: "s", header: "Status", render: (r) => <Badge tone={r.status === "resolved" ? "verified" : "pending"}>{r.status.replace("_", " ")}</Badge> },
          { key: "x", header: "Decision", render: (r) => r.resolution.replace("_", " ") || "None" },
        ]}
        actions={(r) => (
          <>
            <Button variant="tertiary" onClick={() => setOpen(r.public_id)}>Open</Button>
            {r.status !== "resolved" && <Button variant="secondary" onClick={() => { setDeciding(r); setDecision("release"); setPartial(""); }}>Decide</Button>}
          </>
        )}
      />

      <Modal open={!!open} title={`Dispute ${open ?? ""}`} onClose={() => setOpen(null)}>
        {detail.isPending && <p role="status">Loading</p>}
        {detail.data && d && (
          <div className="space-y-3 text-sm">
            <p><strong>Reason:</strong> {d.reason.replace(/_/g, " ")}</p>
            <BuyerBreakdown o={detail.data.order} />
            <ul className="space-y-2">
              {d.evidence.map((e, i) => (
                <li key={i} className="rounded-input bg-ground p-2"><span className="text-xs font-semibold uppercase text-muted">{String(e.by)}</span><p>{e.text ? String(e.text) : "(photo)"}</p></li>
              ))}
            </ul>
            <Timeline events={detail.data.order.timeline} />
            {detail.data.conversation_id && <Button variant="tertiary" onClick={() => setViewChat(detail.data!.conversation_id!)}>Open the order chat</Button>}
          </div>
        )}
      </Modal>
      {viewChat && (
        <ReasonModal open title="Open this private chat?" description="This chat belongs to a disputed order. Your name, the time and your reason are logged." confirmLabel="Open chat" onConfirm={async (reason) => { setChat(await api(`/admin/conversations/${viewChat}`, { query: { reason } })); }} onClose={() => setViewChat(null)} />
      )}
      <Modal open={!!chat} title="Order chat" onClose={() => { setChat(null); setViewChat(null); }}>
        <ul className="max-h-[50dvh] space-y-2 overflow-y-auto">
          {chat?.messages.map((m) => <li key={m.id} className="rounded-input bg-ground p-3 text-sm">{m.body || (m.kind === "payment_request" ? "[Payment request]" : "[Photo]")}</li>)}
        </ul>
      </Modal>

      {deciding && (
        <ReasonModal
          open
          title={`Decide ${deciding.public_id}`}
          description="Both the buyer and the seller are told the result. A full refund returns the commission; a partial refund returns it proportionally."
          confirmLabel="Record decision"
          destructive={decision !== "release"}
          onConfirm={(reason) => {
            const refund = decision === "partial_refund" ? nairaToKobo(Number(partial)) : 0;
            if (decision === "partial_refund" && !(refund > 0)) return Promise.reject(new Error("Enter the amount to refund in naira"));
            return act("POST", `/admin/disputes/${deciding.public_id}/decide`, { decision, refund_item_kobo: refund, reason }, "Decision recorded").then(() => undefined);
          }}
          onClose={() => setDeciding(null)}
        >
          <Select label="Decision" value={decision} onChange={(e) => setDecision(e.target.value as Decision)}>
            <option value="release">Release payment to the seller</option>
            <option value="full_refund">Full refund to the buyer</option>
            <option value="partial_refund">Partial refund to the buyer</option>
          </Select>
          {decision === "partial_refund" && <Input label="Refund amount (₦, of the item price)" inputMode="decimal" value={partial} onChange={(e) => setPartial(e.target.value)} hint={partial ? `Refunds ${naira(nairaToKobo(Number(partial)) || 0)}` : undefined} />}
        </ReasonModal>
      )}
    </>
  );
}
