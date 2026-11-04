import { Star } from "lucide-react";

export function Stars({ rating }: { rating: number }) {
  return (
    <span role="img" aria-label={`${rating} out of 5 stars`} className="inline-flex text-pending-fg">
      {Array.from({ length: 5 }, (_, i) => (
        <Star key={i} size={16} aria-hidden fill={i < rating ? "currentColor" : "none"} />
      ))}
    </span>
  );
}
