// Starts a throw-away API for Playwright: fresh SQLite file, migrations, FAKE dev seed, then uvicorn on :8100.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";

const api = path.resolve(import.meta.dirname, "../../api");
const python = path.join(api, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const exe = existsSync(python) ? python : "python";
const env = {
  ...process.env,
  APP_ENV: "test",
  DATABASE_URL: "sqlite:///./e2e.db",
  AUTH_PROVIDER: "local",
  EXPOSE_DEV_CODES: "true",
  RATE_LIMIT_MULTIPLIER: "1000",
  CORS_ORIGINS: "http://localhost:3100",
  PYTHONPATH: api,
};

rmSync(path.join(api, "e2e.db"), { force: true });
for (const args of [["-m", "alembic", "upgrade", "head"], ["-m", "app.seed_dev"]]) {
  const r = spawnSync(exe, args, { cwd: api, env, stdio: "inherit" });
  if (r.status !== 0) process.exit(r.status ?? 1);
}
spawn(exe, ["-m", "uvicorn", "app.main:app", "--port", "8100"], { cwd: api, env, stdio: "inherit" });

// Stands in for the Render cron job: run due scheduled work (payouts, timeouts, notifications) every few seconds.
setInterval(() => {
  spawnSync(exe, ["-m", "app.jobs.run_due"], { cwd: api, env, stdio: "ignore" });
}, 4000);
