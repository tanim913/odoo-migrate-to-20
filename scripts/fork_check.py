#!/usr/bin/env python3
"""Detect whether a custom module is a (renamed) fork of an Odoo module, and whether that module
exists in Odoo 20.

    fork_check.py <module_dir> [--sources DIR:DIR:...]

A fork is best migrated by REBASING: take the upstream module as it is in Odoo 20, apply the rename,
and replay only the custom delta (the diff between the upstream module at the source version and the
fork). This is far more reliable than porting old code line by line.

Where it looks for upstream modules at the source version: --sources, else $MIG20_OLD_SOURCES
(colon-separated Odoo checkouts or addons directories of older versions, community and enterprise).
Odoo 20 counterparts are looked up in $ODOO20_SERVER / $ODOO20_ENTERPRISE (via env.sh).
"""
import argparse
import ast
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_env():
    keys = ["ODOO20_SERVER", "ODOO20_ENTERPRISE", "MIG20_OLD_SOURCES"]
    out = subprocess.run(["bash", "-c", f'source "{HERE / "env.sh"}" >/dev/null 2>&1; ' + "; ".join(f'echo "${k}"' for k in keys)],
                         capture_output=True, text=True).stdout.splitlines()
    cfg = dict(zip(keys, out + [""] * 3))
    return {k: os.environ.get(k) or cfg.get(k, "") for k in keys}


def addons_dirs(root: Path):
    """An Odoo checkout -> its addons dirs; an addons dir -> itself."""
    if (root / "odoo-bin").exists():
        return [root / "addons", root / "odoo" / "addons"]
    if (root / "odoo" / "odoo-bin").exists():  # e.g. odoo14-server/odoo
        return [root / "odoo" / "addons", root / "odoo" / "odoo" / "addons"]
    return [root]


def model_names(module: Path):
    names = set()
    for py in module.rglob("*.py"):
        if "tests" in py.parts or "__pycache__" in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "_name" for t in node.targets):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    names.add(node.value.value)
    return names


def file_set(module: Path):
    return {str(p.relative_to(module)) for p in module.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and "i18n" not in p.parts}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("module")
    ap.add_argument("--sources")
    args = ap.parse_args()
    module = Path(args.module).resolve()
    cfg = load_env()
    sources = [Path(p) for p in (args.sources or cfg["MIG20_OLD_SOURCES"]).split(":") if p]
    if not sources:
        print("No MIG20_OLD_SOURCES configured: cannot look for an upstream module. "
              "Set it to older Odoo checkouts / enterprise dirs (colon-separated).")
        return 0

    models = model_names(module)
    if not models:
        print("Module defines no new models: fork detection by model names not applicable.")
        return 0
    rx = "|".join(re.escape(m) for m in sorted(models))
    dirs = [str(d) for s in sources for d in addons_dirs(s) if d.is_dir()]
    grep = subprocess.run(["grep", "-rlE", "--include=*.py", rf"_name\s*=\s*['\"]({rx})['\"]", *dirs],
                          capture_output=True, text=True).stdout.splitlines()
    candidates = {}
    for f in grep:
        p = Path(f)
        for parent in p.parents:
            if (parent / "__manifest__.py").exists():
                if parent.resolve() != module:
                    candidates.setdefault(parent, None)
                break
    mine = file_set(module)
    rows = []
    for cand in candidates:
        cm = model_names(cand)
        model_score = len(models & cm) / len(models)
        # compare file names with the module name replaced by the candidate's
        theirs = {f.replace(cand.name, module.name) for f in file_set(cand)}
        file_score = len(mine & theirs) / max(len(mine), 1)
        rows.append((model_score * 0.6 + file_score * 0.4, model_score, file_score, cand))
    rows.sort(reverse=True, key=lambda r: r[0])
    if not rows:
        print(f"No upstream module shares models with {module.name}: not a fork. Migrate normally.")
        return 0

    roots20 = [Path(cfg["ODOO20_SERVER"]) / "addons", Path(cfg["ODOO20_SERVER"]) / "odoo" / "addons"] if cfg["ODOO20_SERVER"] else []
    if cfg["ODOO20_ENTERPRISE"]:
        roots20.append(Path(cfg["ODOO20_ENTERPRISE"]))
    print(f"{module.name}: {len(models)} models, {len(mine)} files\n")
    print(" score  models  files  upstream (source version)          in Odoo 20")
    for score, ms, fs, cand in rows[:5]:
        up20 = next((r / cand.name for r in roots20 if (r / cand.name / "__manifest__.py").exists()), None)
        print(f" {score:5.0%}  {ms:6.0%}  {fs:5.0%}  {str(cand):35s} {up20 or '-'}")
    best = rows[0]
    up20 = next((r / best[3].name for r in roots20 if (r / best[3].name / "__manifest__.py").exists()), None)
    print()
    if best[0] >= 0.6 and up20:
        print(f"VERDICT: FORK of '{best[3].name}'. Rebase strategy recommended:")
        print(f"  1. delta = diff between {best[3]} and {module} (after renaming {best[3].name} -> {module.name})")
        print(f"  2. start from {up20}, rename {best[3].name} -> {module.name} (xmlids, asset paths, python imports, t-name prefixes)")
        print("  3. re-apply only the meaningful parts of the delta; list the rest in MIGRATION_20.md")
        print(f"UPSTREAM_OLD={best[3]}")
        print(f"UPSTREAM_20={up20}")
    elif best[0] >= 0.6:
        print(f"VERDICT: FORK of '{best[3].name}', but that module does not exist in Odoo 20 (removed/merged): migrate normally,")
        print("using the module it was merged into (manifest-and-modules.md) as the reference.")
    else:
        print("VERDICT: partial overlap only (extension or inspired code): migrate normally; the candidates above are good references.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
