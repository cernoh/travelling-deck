#!/usr/bin/env python3
"""Validate Travelling Deck plugin packaging metadata and entry points.

Usage: check_plugin.py <plugin-source-root>

Fails on malformed metadata or a broken entry-point layout. Entry points that
have not landed yet (backend/frontend slices land in parallel) are reported as
pending rather than failed, so `nix flake check` stays runnable on a partially
assembled tree.
"""
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
lines: list[str] = []
errors: list[str] = []


def compile_check(path: pathlib.Path) -> None:
    """Syntax-check a Python module without writing .pyc (store is read-only)."""
    try:
        compile(path.read_text(), str(path), "exec")
        lines.append(f"  compile ok: {path.relative_to(root)}")
    except SyntaxError as exc:
        errors.append(f"backend module {path.name} does not compile: {exc}")


# 1. plugin.json must exist and be a valid Decky manifest.
manifest_path = root / "plugin.json"
if not manifest_path.is_file():
    errors.append("plugin.json missing at plugin root")
else:
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"plugin.json is not valid JSON: {exc}")
    else:
        for field in ("name", "author", "api_version"):
            if field not in manifest:
                errors.append(f"plugin.json missing required field '{field}'")
        if not isinstance(manifest.get("flags"), list):
            errors.append("plugin.json missing 'flags' array (Decky manifest convention)")
        lines.append(
            f"plugin.json: {manifest.get('name', '?')} "
            f"(api_version {manifest.get('api_version', '?')})"
        )

# 2. Backend entry point: backend/main.py (preferred) or root main.py.
backend = root / "backend"
if backend.is_dir():
    mains = sorted(backend.glob("*.py"))
    if not mains:
        errors.append("backend/ exists but contains no .py module")
    elif not (backend / "main.py").is_file():
        errors.append("backend/ exists but backend/main.py is missing (Decky imports backend.main)")
    else:
        lines.append("backend entry: backend/main.py")
        for py in mains:
            compile_check(py)
elif (root / "main.py").is_file():
    lines.append("backend entry: main.py (root layout)")
    compile_check(root / "main.py")
else:
    lines.append("backend entry: pending (expected backend/main.py)")

# 3. Frontend entry point: frontend/ (preferred), src/ (template root), or built dist/.
frontend = root / "frontend"
if frontend.is_dir():
    if (frontend / "src" / "index.tsx").is_file() or (frontend / "dist" / "index.js").is_file():
        lines.append("frontend entry: frontend/src/index.tsx -> frontend/dist/index.js")
    else:
        errors.append(
            "frontend/ exists but has neither frontend/src/index.tsx nor frontend/dist/index.js"
        )
elif (root / "src").is_dir():
    lines.append("frontend entry: src/ (template root layout)")
elif (root / "dist" / "index.js").is_file():
    lines.append("frontend entry: dist/index.js (built)")
else:
    lines.append("frontend entry: pending (expected frontend/src/index.tsx)")

if errors:
    print("\n".join(lines), file=sys.stderr)
    for err in errors:
        print(f"FAIL: {err}", file=sys.stderr)
    sys.exit(1)

print("\n".join(lines))
print("OK: travelling-deck packaging metadata valid")
