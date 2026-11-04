/** Only allow same-site paths as a post-login redirect (blocks open redirects like //evil.com). */
export function safeNext(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return "/";
  return value;
}
