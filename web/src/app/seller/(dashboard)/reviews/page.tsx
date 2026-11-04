"use client";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Field";
import { Stars } from "@/components/reviews/Stars";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import type { components } from "@/lib/api-schema";
import { useAction, useApiQuery } from "@/lib/hooks";

type Review = components["schemas"]["ReviewOut"];

export default function SellerReviews() {
  const reviews = useApiQuery<Review[]>(["seller-reviews"], "/seller/reviews");
  const act = useAction([["seller-reviews"]]);
  const [reply, setReply] = useState<Record<number, string>>({});

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-extrabold md:text-3xl">Reviews</h1>
      {reviews.isPending ? (
        <Skeleton className="h-32" />
      ) : reviews.isError ? (
        <ErrorState message={reviews.error.message} onRetry={() => void reviews.refetch()} />
      ) : reviews.data.length === 0 ? (
        <EmptyState title="No reviews yet" body="After a buyer confirms an order they can rate it. Replies are public and can be sent once." />
      ) : (
        <ul className="space-y-3">
          {reviews.data.map((r) => (
            <li key={r.id}>
              <Card className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Stars rating={r.rating} />
                  <span className="text-sm font-semibold">{r.buyer_first_name}</span>
                  {!r.confirmed_deal && <Badge tone="neutral">Unconfirmed deal</Badge>}
                </div>
                {r.body && <p className="text-sm">{r.body}</p>}
                {r.reply ? (
                  <p className="rounded-input bg-surface p-3 text-sm">
                    <strong>Your reply:</strong> {r.reply}
                  </p>
                ) : (
                  <form
                    className="space-y-2"
                    noValidate
                    onSubmit={(e) => {
                      e.preventDefault();
                      void act("POST", `/reviews/${r.id}/reply`, { reply: reply[r.id] ?? "" }, "Reply sent").catch(() => undefined);
                    }}
                  >
                    <Textarea label="Reply publicly" value={reply[r.id] ?? ""} onChange={(e) => setReply({ ...reply, [r.id]: e.target.value })} hint="You can reply once." />
                    <Button type="submit" variant="secondary" disabled={(reply[r.id] ?? "").trim().length < 2}>
                      Send reply
                    </Button>
                  </form>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
