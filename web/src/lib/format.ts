/** Amounts are integer kobo everywhere; only format at the edge. */
export function naira(kobo: number): string {
  const whole = Math.trunc(kobo / 100);
  const fraction = Math.abs(kobo % 100);
  const text = whole.toLocaleString("en-NG");
  return fraction ? `₦${text}.${String(fraction).padStart(2, "0")}` : `₦${text}`;
}

export function nairaToKobo(naira: number): number {
  return Math.round(naira * 100);
}

export function priceRange(minKobo: number, maxKobo?: number | null): string {
  return maxKobo && maxKobo > minKobo ? `${naira(minKobo)} - ${naira(maxKobo)}` : naira(minKobo);
}

export function timeAgo(iso: string, now = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
