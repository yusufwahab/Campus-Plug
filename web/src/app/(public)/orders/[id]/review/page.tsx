"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import type { Order } from "@/components/orders/parts";
import { ReviewForm } from "@/components/reviews/ReviewForm";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";

function Review() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const client = useQueryClient();
  const order = useQuery({ queryKey: ["order", id], queryFn: () => api<Order>(`/orders/${id}`) });
  if (order.isPending) return <Skeleton className="h-64" />;
  if (order.isError) return <ErrorState message={order.error.message} onRetry={() => void order.refetch()} />;
  const o = order.data;
  if (!o.can_review) {
    return (
      <Card className="mx-auto max-w-xl space-y-3">
        <h1 className="text-2xl font-extrabold">You cannot review this order</h1>
        <p className="text-sm text-muted">Reviews open once an order is completed, and each order can be reviewed once.</p>
        <Button href={`/orders/${o.public_id}`}>Back to the order</Button>
      </Card>
    );
  }
  return (
    <Card className="mx-auto max-w-xl space-y-4">
      <h1 className="text-2xl font-extrabold">Review {o.listing_title}</h1>
      <ReviewForm
        path={`/orders/${id}/review`}
        onDone={() => {
          void client.invalidateQueries({ queryKey: ["order", id] });
          router.push(`/orders/${id}`);
        }}
      />
    </Card>
  );
}

export default function ReviewPage() {
  return (
    <RequireAuth>
      <Review />
    </RequireAuth>
  );
}
