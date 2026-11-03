import type { Metadata } from "next";
import { StatusPage } from "@/components/layout/StatusPage";
import { RetryButton } from "./RetryButton";

export const metadata: Metadata = { title: "You are offline" };

export default function OfflinePage() {
  return (
    <StatusPage
      code="Offline"
      title="No connection"
      body="Browsing saved pages still works. Payments and other money actions need a connection."
      actions={<RetryButton />}
    />
  );
}
