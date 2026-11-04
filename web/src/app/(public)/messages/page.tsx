"use client";
import { ChatShell } from "@/components/chat/ChatShell";
import { RequireAuth } from "@/lib/auth";

export default function MessagesPage() {
  return (
    <RequireAuth>
      <ChatShell basePath="/messages" />
    </RequireAuth>
  );
}
