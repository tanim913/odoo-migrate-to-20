#!/usr/bin/env python3
"""Rebase a forked module onto its upstream Odoo 20 version (see fork_check.py).

    rebase_fork.py <upstream_20_module_dir> <dest_module_dir> [--keep-manifest-keys name,license,...]

Replaces the content of <dest_module_dir> (the migrated copy, already committed as a baseline by
prepare.sh) with the upstream Odoo 20 module, renamed from the upstream technical name to the
dest's name:
  - xmlids / template names / groups:  upstream.xyz   -> dest.xyz
  - asset paths and URLs:              upstream/static -> dest/static, /upstream/static -> /dest/static
  - JS module paths:                   @upstream/      -> @dest/
  - Python imports:                    odoo.addons.upstream -> odoo.addons.dest
Model names (upstream.media, upstream.post, ... any `_name`/`_inherit` defined or used as a model)
are NOT renamed, so the fork keeps its database schema.

Manifest keys listed in --keep-manifest-keys (default: name, author, website, and any
key unknown to Odoo) are taken from the old dest manifest. Everything else comes from upstream 20.
Afterwards, re-apply the fork's meaningful custom delta by hand, then run the normal install loop.

Prints every remaining occurrence of the upstream name for manual review.
"""
import argparse
import ast
import re
import shutil
import sys
from pathlib import Path

TEXT_EXT = {".py", ".xml", ".js", ".scss", ".css", ".csv", ".po", ".pot", ".json", ".md", ".rst", ".txt", ".html"}
ODOO_MANIFEST_KEYS = {
    "name", "version", "category", "sequence", "summary", "description", "website", "author", "license",
    "depends", "data", "demo", "assets", "installable", "application", "auto_install", "external_dependencies",
    "images", "pre_init_hook", "post_init_hook", "uninstall_hook", "post_load", "countries", "price", "currency",
    "maintainer", "contributors", "live_test_url", "web_icon", "icon", "bootstrap", "cloc_exclude", "configurator_snippets",
    "new_page_templates", "iap_paid_service", "snippet_lists", "theme_customizations",
}


def model_names(root: Path):
    names = set()
    for py in root.rglob("*.py"):
        text = py.read_text(errors="replace")
        for m in re.finditer(r"_(?:name|inherit)\s*=\s*\[?\s*['\"]([\w.]+)['\"]", text):
            names.add(m.group(1))
        for m in re.finditer(r"fields\.(?:Many2one|One2many|Many2many)\(\s*['\"]([\w.]+)['\"]", text):
            names.add(m.group(1))
        for m in re.finditer(r"comodel_name\s*=\s*['\"]([\w.]+)['\"]", text):
            names.add(m.group(1))
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("upstream")
    ap.add_argument("dest")
    ap.add_argument("--keep-manifest-keys", default="name,author,website")
    args = ap.parse_args()
    up = Path(args.upstream).resolve()
    dest = Path(args.dest).resolve()
    old, new = up.name, dest.name
    if old == new:
        print("upstream and dest have the same name: plain copy, nothing to rename")

    old_manifest = ast.literal_eval((dest / "__manifest__.py").read_text())
    keep = {k for k in args.keep_manifest_keys.split(",") if k} | {k for k in old_manifest if k not in ODOO_MANIFEST_KEYS}

    models = model_names(up)
    # every dotted token starting with "<old>." that is a model name (or a prefix of one) is protected
    protected = sorted({m for m in models if m.startswith(old + ".")}, key=len, reverse=True)

    # replace dest content (keep .git-less baseline commit for the diff)
    for child in dest.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    shutil.copytree(up, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    tok = re.compile(rf"(?<![\w./-]){re.escape(old)}\.([A-Za-z_][\w.]*)")
    rules = [
        (re.compile(rf"(?<![\w-])/{re.escape(old)}/static/"), f"/{new}/static/"),
        (re.compile(rf"(?<![\w/.-]){re.escape(old)}/static/"), f"{new}/static/"),
        (re.compile(rf"@{re.escape(old)}/"), f"@{new}/"),
        (re.compile(rf"odoo\.addons\.{re.escape(old)}\b"), f"odoo.addons.{new}"),
        (re.compile(rf"(module\s*=\s*|module['\"]\s*,\s*['\"]=['\"]\s*,\s*)(['\"]){re.escape(old)}\2"), rf"\1\2{new}\2"),
    ]
    counts = {"xmlid/template": 0, "paths/imports": 0}
    for f in dest.rglob("*"):
        if not f.is_file() or f.suffix not in TEXT_EXT:
            continue
        text = f.read_text(errors="replace")
        orig = text
        for rx, repl in rules:
            text, n = rx.subn(repl, text)
            counts["paths/imports"] += n

        def swap(m):
            full = f"{old}.{m.group(1)}".rstrip(".")
            if any(full == p or full.startswith(p + ".") for p in protected):
                return m.group(0)  # a model name: keep the schema
            counts["xmlid/template"] += 1
            return f"{new}.{m.group(1)}"
        text = tok.sub(swap, text)
        if text != orig:
            f.write_text(text)

    # i18n: rename the .pot file
    for pot in (dest / "i18n").glob(f"{old}.pot") if (dest / "i18n").exists() else []:
        pot.rename(pot.with_name(f"{new}.pot"))

    # manifest: upstream 20, with the fork's kept keys
    mpath = dest / "__manifest__.py"
    text = mpath.read_text()
    manifest = ast.literal_eval(text)
    for k in keep:
        if k in old_manifest:
            manifest[k] = old_manifest[k]
    lines = ["# -*- coding: utf-8 -*-", f"# Rebased on upstream '{old}' (Odoo 20) by odoo-migrate-to-20/rebase_fork.py", "{"]
    for k, v in manifest.items():
        lines.append(f"    {k!r}: {v!r},")
    lines.append("}")
    mpath.write_text("\n".join(lines) + "\n")

    up_license = ast.literal_eval((up / "__manifest__.py").read_text()).get("license")
    if old_manifest.get("license") and old_manifest.get("license") != up_license:
        print(f"LICENSE: the fork declared {old_manifest.get('license')!r} but the upstream code is {up_license!r}; "
              f"kept upstream's. Report this to the user (e.g. OEEL-1 enterprise code cannot be relicensed as LGPL).")
    print(f"rebased {new} on {up}")
    print(f"renamed: {counts}; protected model names: {', '.join(protected) or '-'}")
    print(f"manifest keys kept from the fork: {', '.join(sorted(k for k in keep if k in old_manifest))}")
    print(f"\nremaining '{old}' occurrences to review (model names and prose are expected):")
    for f in sorted(dest.rglob("*")):
        if f.is_file() and f.suffix in TEXT_EXT and f.suffix not in (".po", ".pot"):
            for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                for m in re.finditer(rf"(?<![\w]){re.escape(old)}(?![\w])[^\s'\"]*", line):
                    t = m.group(0)
                    if any(t.startswith(p) for p in protected):
                        continue
                    print(f"  {f.relative_to(dest)}:{i}: {line.strip()[:140]}")
                    break
    return 0


if __name__ == "__main__":
    sys.exit(main())
