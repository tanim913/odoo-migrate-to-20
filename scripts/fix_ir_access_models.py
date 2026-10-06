#!/usr/bin/env python3
"""Replace model xmlids left in ir.access.csv files by Odoo's 19.4 converter with model names.

    fix_ir_access_models.py <addons_paths(comma)> <module_dir> [...]

The converter sometimes writes `module.model_sale_order` or `model_sale_order` in the model_id
column, which Odoo 20 cannot resolve (it expects `sale.order`). Model names are taken from every
`_name = "..."` in the given addons paths; `model_a_b_c` is matched against them.
"""
import csv
import io
import re
import sys
from pathlib import Path

paths = [Path(p) for p in sys.argv[1].split(",")]
names = set()
for base in paths:
    for py in base.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        for m in re.finditer(r"""^\s+_name\s*=\s*['"]([\w.]+)['"]""", py.read_text(errors="replace"), re.M):
            names.add(m.group(1))
by_xmlname = {}
for n in names:
    by_xmlname.setdefault("model_" + n.replace(".", "_"), set()).add(n)

exit_code = 0
for arg in sys.argv[2:]:
    f = Path(arg) / "security" / "ir.access.csv"
    if not f.exists():
        continue
    rows = list(csv.reader(io.StringIO(f.read_text())))
    changed = 0
    for r in rows[1:]:
        if not r or len(r) < 3:
            continue
        val = r[2].strip()
        local = val.split(".", 1)[1] if "." in val and val.split(".", 1)[1].startswith("model_") else val
        if local.startswith("model_"):
            cands = by_xmlname.get(local, set())
            if len(cands) == 1:
                r[2] = next(iter(cands))
                changed += 1
            else:
                print(f"{f}: cannot resolve {val} (candidates: {sorted(cands)})")
                exit_code = 1
    if changed:
        out = io.StringIO()
        csv.writer(out, lineterminator="\n").writerows(rows)
        f.write_text(out.getvalue())
    print(f"{f}: {changed} model ids fixed")
sys.exit(exit_code)
