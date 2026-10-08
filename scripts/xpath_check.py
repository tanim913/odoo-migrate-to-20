"""List every view locator of a module that Odoo 20 cannot apply, in one run.

Run in `odoo-bin shell` on a database where the module's dependencies are installed (the module
itself does not need to be installed). Nothing is committed.

    MODULE_DIR=/path/to/module odoo-bin shell -d DB --no-http < xpath_check.py

The module's view records are inserted with SQL (no validation), then each primary view they
touch is combined with Odoo's own order (priority, id; depth first; primary children last).
Each spec node is applied separately, so one failing locator does not hide the next ones. Field
existence is not checked (the module's models are not loaded), only the locators.

--addons-path must contain the folder of every module installed in that database (test helper
modules included), or the shell stops before running the script and prints no result line.
"""
import collections
import copy
import json
import os
import re
from pathlib import Path

from lxml import etree

from odoo.tools.convert import _fix_multiple_roots
from odoo.tools.template_inheritance import apply_inheritance_specs, locate_node

module_dir = Path(os.environ['MODULE_DIR'])
module = module_dir.name
manifest = eval((module_dir / '__manifest__.py').read_text())  # noqa: S307 - local trusted file
View = env['ir.ui.view']  # noqa: F821 - odoo shell global
cr = env.cr  # noqa: F821
XMLID_RE = re.compile(r'%\(([\w.]+)\)[ds]')
problems = []
ids = {}      # xmlid -> view id
meta = {}     # view id -> (rel, xmlid)


def full(xmlid):
    return xmlid if '.' in xmlid else f'{module}.{xmlid}'


def ref_id(xmlid):
    xmlid = full(xmlid)
    if xmlid in ids:
        return ids[xmlid]
    rec = env.ref(xmlid, raise_if_not_found=False)  # noqa: F821
    return rec.id if rec else None


def resolve(text):
    return XMLID_RE.sub(lambda m: str(ref_id(m.group(1)) or m.group(0)), text)


cr.execute('SAVEPOINT xpath_check')
for rel in manifest.get('data', []):
    path = module_dir / rel
    if path.suffix != '.xml' or not path.exists():
        continue
    try:
        tree = etree.parse(str(path))
    except etree.XMLSyntaxError as e:
        problems.append(f'{rel}: XML syntax error {e}')
        continue
    for rec in tree.iter('record', 'template'):
        if rec.tag == 'template':
            # QWeb template: <template inherit_id=...> children are the spec (like the importer)
            xmlid = full(rec.get('id'))
            inherit_ref = rec.get('inherit_id')
            body = etree.Element('data')
            for child in rec:
                body.append(copy.deepcopy(child))
            if not inherit_ref:
                t = etree.Element('t', {'t-name': xmlid})
                for child in rec:
                    t.append(copy.deepcopy(child))
                body = t
            arch = resolve(etree.tostring(body, encoding='unicode'))
            parent = ref_id(inherit_ref) if inherit_ref else None
            if inherit_ref and not parent:
                problems.append(f'{rel}:{rec.sourceline} {xmlid}: parent {inherit_ref} not found')
                continue
            try:
                priority = int(rec.get('priority', 16))
            except ValueError:
                priority = 16
            mode = 'primary' if (rec.get('primary') or not parent) else 'extension'
            model = None
        else:
            if rec.get('model') != 'ir.ui.view':
                continue
            arch_f = rec.find("field[@name='arch']")
            if arch_f is None or not any(isinstance(n.tag, str) for n in arch_f):
                continue
            xmlid = full(rec.get('id'))
            node = copy.deepcopy(arch_f)
            _fix_multiple_roots(node)  # same as the XML importer
            arch = resolve("".join(etree.tostring(n, encoding='unicode') for n in node))
            inherit = rec.find("field[@name='inherit_id']")
            parent = ref_id(inherit.get('ref')) if inherit is not None else None
            if inherit is not None and not parent:
                problems.append(f'{rel}:{rec.sourceline} {xmlid}: parent {inherit.get("ref")} not found')
                continue
            prio = rec.find("field[@name='priority']")
            try:
                priority = int((prio.get('eval') or prio.text or '16').strip()) if prio is not None else 16
            except ValueError:
                priority = 16
            mode_f = rec.find("field[@name='mode']")
            mode = mode_f.text if mode_f is not None else ('extension' if parent else 'primary')
            model_f = rec.find("field[@name='model']")
            model = model_f.text if model_f is not None else None
        existing = env.ref(xmlid, raise_if_not_found=False)  # noqa: F821 - also when the module is installed
        if existing:
            cr.execute("UPDATE ir_ui_view SET arch_db=%s, inherit_id=%s, priority=%s, mode=%s WHERE id=%s",
                       (json.dumps({'en_US': arch}), parent, priority, mode, existing.id))
            vid = existing.id
        else:
            cr.execute("""INSERT INTO ir_ui_view (name, key, model, type, arch_db, inherit_id, priority, mode, active, visibility)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true, 'public') RETURNING id""",
                       (xmlid, xmlid, model, ('qweb' if rec.tag == 'template' else etree.fromstring(arch.strip()).tag) if not parent else None,
                        json.dumps({'en_US': arch}), parent, priority, mode))
            vid = cr.fetchone()[0]
        ids[xmlid] = vid
        meta[vid] = (rel, xmlid)
env.invalidate_all()  # noqa: F821
env.registry.clear_cache('templates') if hasattr(env.registry, 'clear_cache') else None  # noqa: F821


def parse(arch):
    return etree.fromstring((arch or '<data/>').strip())


def apply_view(view, combined):
    """Apply the spec nodes of `view` one by one; record failures of the module's views only."""
    try:
        spec = parse(view.arch)
    except etree.XMLSyntaxError as e:
        problems.append(f'view {view.xml_id or view.name} ({view.id}): arch unreadable: {e}')
        return combined
    for node in (list(spec) if spec.tag == 'data' else [spec]):
        if not isinstance(node.tag, str):
            continue
        own = view.id in meta
        if own and locate_node(combined, node) is None:
            rel, xmlid = meta[view.id]
            loc = node.get('expr') or f"<{node.tag} name={node.get('name')!r}>"
            problems.append(f"{rel} {xmlid}: cannot locate {loc}")
            continue
        try:
            wrapper = etree.Element('data')
            wrapper.append(copy.deepcopy(node))
            combined = apply_inheritance_specs(combined, wrapper)
        except Exception as e:  # noqa: BLE001
            if own:
                problems.append(f"{meta[view.id][1]}: apply failed: {e}")
    return combined


def children_of(view):
    return View.search([('inherit_id', '=', view.id), ('mode', '=', 'extension'), ('active', '=', True)],
                       order='priority, id')


cache = {}


def combine(primary):
    """Combined arch of a primary view, like ir.ui.view._get_combined_arch."""
    if primary.id in cache:
        return copy.deepcopy(cache[primary.id])
    if primary.inherit_id:
        parent = primary.inherit_id
        while parent.mode != 'primary' and parent.inherit_id:
            parent = parent.inherit_id
        combined = apply_view(primary, combine(parent))
    else:
        try:
            combined = parse(primary.arch)
        except etree.XMLSyntaxError as e:
            problems.append(f'root {primary.xml_id or primary.name}: arch unreadable: {e}')
            return etree.Element('data')
    queue = collections.deque(children_of(primary))
    while queue:
        view = queue.popleft()
        combined = apply_view(view, combined)
        queue.extendleft(reversed(children_of(view)))
    cache[primary.id] = combined
    return copy.deepcopy(combined)


def primary_of(view):
    while view.mode != 'primary' and view.inherit_id:
        view = view.inherit_id
    return view


for vid in meta:
    combine(primary_of(View.browse(vid)))
cr.execute('ROLLBACK TO SAVEPOINT xpath_check')
for p in dict.fromkeys(problems):
    print(p)
print(f'XPATH_CHECK {module}: {len(dict.fromkeys(problems))} problem(s)')
