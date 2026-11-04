"use client";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ChatShell } from "@/components/chat/ChatShell";
import { Thread } from "@/components/chat/Thread";
import { ReviewForm } from "@/components/reviews/ReviewForm";
import { Card } from "@/components/ui/Card";
import { RequireAuth } from "@/lib/auth";

/** Shown when the buyer follows the "Did you buy from this seller?" notification. */
function UnconfirmedReview({ id }: { id: number }) {
  const wanted = useSearchParams().get("review") === "1";
  const [done, setDone] = useState(false);
  if (!wanted || done) return null;
  return (
    <Card className="m-3 space-y-3">
      <h2 className="text-lg font-bold">Did you buy from this seller?</h2>
      <ReviewForm
        path={`/conversations/${id}/review`}
        onDone={() => setDone(true)}
        intro="Deals made outside the app show as Unconfirmed deal and count for less in the shop rating."
      />
    </Card>
  );
}

export default function ThreadPage() {
  const id = Number(useParams<{ id: string }>().id);
  return (
    <RequireAuth>
      <ChatShell activeId={id} basePath="/messages">
        <Suspense fallback={null}>
          <UnconfirmedReview id={id} />
        </Suspense>
        <Thread id={id} />
      </ChatShell>
    </RequireAuth>
  );
}
