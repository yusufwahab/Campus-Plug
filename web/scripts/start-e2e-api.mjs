// Starts a throw-away API for Playwright: fresh SQLite file, migrations, FAKE dev seed, then uvicorn on :8100.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";

const api = path.resolve(import.meta.dirname, "../../api");
const python = path.join(api, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const exe = existsSync(python) ? python : "python";
const env = {
  ...process.env,
  // Every setting is pinned so a developer's api/.env (real database, payment or email keys) can never leak into a test run.
  APP_ENV: "test",
  DATABASE_URL: "sqlite:///./e2e.db",
  JWT_SECRET: "e2e-only-secret-not-used-anywhere-else-0123456789",
  EXPOSE_DEV_CODES: "true",
  PAYMENT_PROVIDER: "local",
  PAYSTACK_SECRET_KEY: "",
  EMAIL_PROVIDER: "local",
  BREVO_API_KEY: "",
  EMAIL_FROM: "",
  STORAGE_PROVIDER: "local",
  CLOUDINARY_CLOUD_NAME: "",
  CLOUDINARY_API_KEY: "",
  CLOUDINARY_API_SECRET: "",
  FEATURE_SMS: "false",
  VAPID_PRIVATE_KEY: "",
  VAPID_PUBLIC_KEY: "",
  WEB_URL: "http://localhost:3100",
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
