"use client";
import { useParams } from "next/navigation";
import { ChatShell } from "@/components/chat/ChatShell";
import { Thread } from "@/components/chat/Thread";

export default function SellerThread() {
  const id = Number(useParams<{ id: string }>().id);
  return (
    <ChatShell activeId={id} basePath="/seller/messages">
      <Thread id={id} />
    </ChatShell>
  );
}
