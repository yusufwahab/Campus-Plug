"use client";
import { StatusPage } from "@/components/layout/StatusPage";
import { Button } from "@/components/ui/Button";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <StatusPage
      code="500"
      title="Something went wrong on our side"
      body="We have been notified. Try again, or head back to the marketplace."
      actions={
        <>
          <Button onClick={reset}>Try again</Button>
          <Button href="/" variant="tertiary">
            Home
          </Button>
        </>
      }
    />
  );
}
