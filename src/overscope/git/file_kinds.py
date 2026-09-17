from __future__ import annotations

import re
from pathlib import PurePosixPath

MANIFEST_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "gemfile",
    "go.mod",
    "cargo.toml",
}
LOCKFILE_NAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "uv.lock",
    "poetry.lock",
    "pipfile.lock",
    "gemfile.lock",
    "go.sum",
    "cargo.lock",
}
SECURITY_TOKENS = {
    "auth",
    "authentication",
    "authenticate",
    "authorization",
    "authorize",
    "authn",
    "authz",
    "oauth",
    "security",
    "credential",
    "credentials",
    "rbac",
    "keycloak",
}
ENVIRONMENT_TOKENS = {"secrets", "secret", "credentials", "keystore", "keychain"}

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")

def classify_file(path: str) -> str:
    normalized = path.replace("\\", "/").lower()
    item = PurePosixPath(normalized)
    name = item.name
    parts = set(item.parts)
    tokens = _segment_tokens(path)

    if _is_test(normalized, name, parts):
        return "test"
    if name in LOCKFILE_NAMES:
        return "lockfile"
    if name in MANIFEST_NAMES:
        return "dependency"
    if "migration" in parts or "migrations" in parts or name.startswith(("migration", "migrate")):
        return "migration"
    if name == ".env" or name.startswith(".env.") or tokens & ENVIRONMENT_TOKENS:
        return "environment"
    if tokens & SECURITY_TOKENS:
        return "security"
    if name.endswith((".md", ".mdx", ".rst")) or "docs" in parts or "doc" in parts:
        return "documentation"
    if name.endswith((".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".json")):
        return "config"
    generated_dirs = {"dist", "build", "coverage", "generated", "vendor", "node_modules"}
    if parts & generated_dirs:
        return "generated"
    return "source"

def _segment_tokens(path: str) -> set[str]:
    """Split a path into lowercase word tokens, respecting camelCase and separators.

    ``src/AuthToken.py`` -> {src, auth, token, py}; ``blog/authors/list.py`` keeps
    ``authors`` as a single token so it never matches the security vocabulary.
    """
    tokens: set[str] = set()
    for part in PurePosixPath(path).parts:
        spaced = _CAMEL_BOUNDARY.sub(" ", part)
        for token in _NON_ALNUM.split(spaced):
            if token:
                tokens.add(token.lower())
    return tokens

def _is_test(path: str, name: str, parts: set[str]) -> bool:
    return (
        "test" in parts
        or "tests" in parts
        or "__tests__" in parts
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", ".spec.js"))
        or "/test/" in path
    )
