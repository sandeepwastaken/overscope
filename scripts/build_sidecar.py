"""Build the Python analyzer as a platform-specific Tauri sidecar.

End users receive one native application bundle. They do not need Python, uv, or a
virtual environment; PyInstaller embeds the interpreter and Overscope package into the
sidecar that Tauri signs and ships with the desktop app.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARIES = ROOT / "web" / "src-tauri" / "binaries"

def target_triple() -> str:
    machine = platform.machine().lower()
    arch = "aarch64" if machine in {"arm64", "aarch64"} else "x86_64"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    if sys.platform == "win32":
        return f"{arch}-pc-windows-msvc"
    if sys.platform.startswith("linux"):
        return f"{arch}-unknown-linux-gnu"
    raise SystemExit(f"Unsupported sidecar build platform: {sys.platform} / {machine}")

def main() -> None:
    triple = os.environ.get("TAURI_ENV_TARGET_TRIPLE") or target_triple()
    extension = ".exe" if "windows" in triple else ""
    BINARIES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="overscope-sidecar-") as directory:
        work = Path(directory)
        subprocess.run(
            [
                "uv",
                "run",
                "--with",
                "pyinstaller>=6.11,<7",
                "pyinstaller",
                "--noconfirm",
                "--clean",
                "--onefile",
                "--name",
                "overscope-engine",
                "--paths",
                str(ROOT / "src"),
                "--distpath",
                str(work / "dist"),
                "--workpath",
                str(work / "build"),
                "--specpath",
                str(work / "spec"),
                str(ROOT / "src" / "overscope" / "__main__.py"),
            ],
            cwd=ROOT,
            check=True,
        )
        source = work / "dist" / f"overscope-engine{extension}"
        destination = BINARIES / f"overscope-engine-{triple}{extension}"
        shutil.copy2(source, destination)
        destination.chmod(destination.stat().st_mode | 0o111)
        print(f"Built {destination.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
