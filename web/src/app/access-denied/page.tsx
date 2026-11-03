import type { Metadata } from "next";
import { StatusPage } from "@/components/layout/StatusPage";
import { Button } from "@/components/ui/Button";

export const metadata: Metadata = { title: "Access denied" };

export default function AccessDenied() {
  return (
    <StatusPage
      code="403"
      title="You do not have access to this page"
      body="Your account does not have the permission needed here. If you think this is a mistake, contact support."
      actions={
        <>
          <Button href="/">Back to marketplace</Button>
          <Button href="/contact" variant="tertiary">
            Contact support
          </Button>
        </>
      }
    />
  );
}
