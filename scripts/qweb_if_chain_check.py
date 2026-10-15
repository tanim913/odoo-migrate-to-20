"""Find QWeb pages where an inherited view separated a `t-else` / `t-elif` from its `t-if`.

An xpath `position="after"` on an element with `t-if` inserts its content between that element and
its `t-else`; QWeb then refuses to render the page ("t-elif directive must be preceded by t-if"). The
error only shows when the page is opened. Run in `odoo-bin shell` on a database with the modules:

    odoo-bin shell -d DB --no-http < qweb_if_chain_check.py
"""
from lxml import etree

bad = []
views = env['ir.ui.view'].search([('type', '=', 'qweb'), ('mode', '=', 'primary')])  # noqa: F821
for view in views:
    try:
        arch = etree.fromstring(view.with_context(lang=None).get_combined_arch())
    except Exception as e:  # noqa: BLE001
        bad.append((view.key or view.name, 'ERROR', str(e)[:100]))
        continue
    for el in arch.iter():
        if not isinstance(el.tag, str) or not ('t-else' in el.attrib or 't-elif' in el.attrib):
            continue
        prev = el.getprevious()
        while prev is not None and not isinstance(prev.tag, str):
            prev = prev.getprevious()
        if prev is None or not ('t-if' in prev.attrib or 't-elif' in prev.attrib):
            bad.append((view.key or view.name, el.tag, etree.tostring(el)[:120]))
for item in bad:
    print('QWEB_IF_CHAIN', item)
print(f'QWEB_IF_CHAIN_CHECK: {len(views)} pages, {len(bad)} problem(s)')
