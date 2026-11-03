import next from "eslint-config-next";

const config = [
  ...next,
  { ignores: ["public/sw.js", ".next/**", "src/lib/api-schema.d.ts", "playwright-report/**"] },
];

export default config;
