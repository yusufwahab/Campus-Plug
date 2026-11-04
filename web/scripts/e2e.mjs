// Builds the web app against the e2e API URL, then runs Playwright. Pass --no-build to reuse the last build.
// Journeys change shared data (stock, orders, bans), so with no --project flag each screen size runs against its own
// freshly seeded database, one after the other.
import { spawnSync } from "node:child_process";

const args = process.argv.slice(2);
const skipBuild = args.includes("--no-build");
const rest = args.filter((a) => a !== "--no-build");
const env = { ...process.env, NEXT_PUBLIC_API_URL: "http://localhost:8100/api/v1", NEXT_PUBLIC_SITE_URL: "http://localhost:3100" };
const run = (cmd, a) => spawnSync(cmd, a, { env, stdio: "inherit", shell: true }).status ?? 1;

if (!skipBuild && run("npm", ["run", "build"]) !== 0) process.exit(1);

const pickedProject = rest.some((a) => a === "--project" || a.startsWith("--project="));
const projects = pickedProject ? [null] : ["mobile", "tablet", "desktop"];
let failed = 0;
for (const project of projects) {
  const extra = project ? [`--project=${project}`] : []; // "=" form: --project is variadic and would swallow spec file names
  if (run("npx", ["playwright", "test", ...extra, ...rest]) !== 0) failed = 1;
}
process.exit(failed);
