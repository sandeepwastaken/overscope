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

Prerequisites are Node 20+, Rust stable, Git, Python 3.12+, and uv.

```bash
cd web
npm install
npm run desktop:dev
```

Browser-only visual development uses the adversarial sample and needs no Rust toolchain:

```bash
npm run dev
```

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
