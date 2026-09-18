# Overscope desktop

The desktop client is a React interface inside a Tauri 2 shell. It consumes the exact
same `schema_version: 1.0` report as `overscope --json`; scope, rules, and reconciliation
logic remain in the Python package.

## Architecture

- **React:** situation overview, changed-file navigation, hunk-level diff, claim ledger,
  and raw evidence console.
- **Rust/Tauri:** native repository picker, constrained IPC, sidecar lifecycle, and safe
  Finder/Explorer reveal behavior.
- **Python sidecar:** the CLI is frozen into one platform executable by PyInstaller.
  Installed applications therefore do not require Python, uv, or `.venv`.

The Rust boundary accepts only a repository path and optional session/agent overrides.
It executes the analyzer with an argument array—never a shell command—and parses the
JSON before returning it to React.

## Development

There are two ways to run it, depending on whether you want the real desktop app or just
the interface.

### Browser preview (no Rust)

The fast path. Runs the React UI against bundled sample data, so it needs nothing but
Node:

```bash
cd web
npm install
npm run dev
```

### The desktop app

This compiles the native Tauri (Rust) shell and freezes the Python analyzer into a
sidecar, so it needs two more tools:

- **Rust** (stable) — `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`, then
  reopen your terminal. On Windows, install rustup from <https://rustup.rs/>.
- **uv** — <https://docs.astral.sh/uv/> (used to build the Python sidecar).

Then:

```bash
cd web
npm install
npm run desktop:dev
```

The first `desktop:dev` compiles the Rust shell from scratch and can take a few minutes;
later runs are quick. If Rust or uv is missing, the command tells you which one and how to
install it instead of failing with a compiler error.

## Distribution

Build on each target operating system; Tauri and PyInstaller do not cross-compile these
artifacts reliably:

```bash
cd web
npm ci
npm run desktop:build
```

This produces a signed-ready `.app`/`.dmg` on macOS and `.msi`/`.exe` installer on
Windows under `web/src-tauri/target/release/bundle/`. Signing identities are supplied by
the release environment and are intentionally not stored in this repository.
