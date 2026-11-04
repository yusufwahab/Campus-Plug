"use client";
import { useParams } from "next/navigation";
import { OrderDetail } from "@/components/orders/OrderDetail";

export default function SellerOrderPage() {
  const { id } = useParams<{ id: string }>();
  return <OrderDetail id={id} base="seller" />;
}
