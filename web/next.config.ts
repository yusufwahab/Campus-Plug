import withSerwistInit from "@serwist/next";
import type { NextConfig } from "next";

const withSerwist = withSerwistInit({
  swSrc: "src/app/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",
});

const apiOrigin = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/api\/v1\/?$/, "");
const isDev = process.env.NODE_ENV === "development";
// Next injects small inline scripts and styles, so script/style allow 'unsafe-inline'. Everything else is locked to
// this site, the API, and Supabase (Realtime and Storage).
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${apiOrigin} https://*.supabase.co`,
  `connect-src 'self' ${apiOrigin} https://*.supabase.co wss://*.supabase.co`,
  "worker-src 'self'",
  "manifest-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const config: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
  reactStrictMode: true,
  // Always put metadata in <head> (never streamed) so link previews and crawlers read titles and Open Graph tags.
  htmlLimitedBots: /.*/,
  images: { remotePatterns: [{ protocol: "https", hostname: "**.supabase.co" }] },
};

export default withSerwist(config);
