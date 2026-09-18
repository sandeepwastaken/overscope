// Toolchain check for the desktop build. Fails with a plain-language message that
// names the missing tool and how to get it, instead of a raw cargo/uv error.

import { spawnSync } from "node:child_process";

function has(command) {
  const result = spawnSync(command, ["--version"], { stdio: "ignore" });
  return !result.error && result.status === 0;
}

const missing = [];

if (!has("cargo")) {
  missing.push({
    tool: "Rust (cargo)",
    reason: "Tauri compiles a native Rust shell around the app.",
    install:
      process.platform === "win32"
        ? "Install rustup from https://rustup.rs/, then reopen your terminal."
        : "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh   (then reopen your terminal)",
  });
}

if (!has("uv")) {
  missing.push({
    tool: "uv",
    reason: "The Python analyzer is frozen into a sidecar binary with it.",
    install: "Install from https://docs.astral.sh/uv/getting-started/installation/",
  });
}

if (missing.length > 0) {
  const rule = "─".repeat(64);
  const out = [
    "",
    rule,
    "Can't build the Overscope desktop app yet. Missing:",
    "",
    ...missing.flatMap((item) => [`  • ${item.tool} — ${item.reason}`, `      ${item.install}`, ""]),
    "Just want to see the UI? That needs none of this:",
    "      npm run dev",
    rule,
    "",
  ].join("\n");
  process.stderr.write(out);
  process.exit(1);
}
