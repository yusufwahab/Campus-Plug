"use client";
import { useParams } from "next/navigation";
import { OrderDetail } from "@/components/orders/OrderDetail";
import { RequireAuth } from "@/lib/auth";

export default function OrderPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RequireAuth>
      <OrderDetail id={id} base="buyer" />
    </RequireAuth>
  );
}
