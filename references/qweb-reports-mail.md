# Server-side QWeb (website pages, reports, portal) and mail templates

## `t-esc` / `t-raw` render NOTHING in 20 (silent)

- 20's `ir_qweb.py` has no `t-esc` or `t-raw` directive. A leftover only logs
  `Unknown directives or unused attributes` and the node **outputs nothing**: a blank report
  field, an empty page title, an empty price.
- `t-raw` has been deprecated since 16; `t-esc` still worked through 19.
- No upgrade script touches server templates (`views/`, `report/`, `data/`). The owl3 script only
  touches `static/`.

| Old | Odoo 20 |
|---|---|
| `<span t-esc="o.name"/>` | `<span t-out="o.name"/>` (escaped) |
| `<div t-raw="o.description"/>` | `<div t-out="o.description"/>`. `Html` fields and `Markup` values are rendered unescaped; a plain `str` containing HTML must be wrapped in `markupsafe.Markup(...)` in Python (only for trusted content) |
| `t-esc="x" t-options="{'widget': 'monetary', ...}"` | `t-out="x" t-options="..."` (t-options unchanged) |
| `t-field="o.x"` | unchanged |
| `t-att-*`, `t-attf-*`, `t-if`, `t-foreach` | unchanged |

Rewrite every `t-esc=` → `t-out=` and `t-raw=` → `t-out=` in all non-static XML. This is
mechanical and safe; the `scan.py --fix-tesc` option does it. For each `t-raw`, check whether the
value is HTML that is not already an Html field or Markup: if so, wrap it in Python with `Markup`
(trusted content only) or keep it escaped.

## `t-call` body `t-set` no longer reaches the callee (silent)

- 19 kept a deprecated path; 20 removed it.
- Old: `<t t-call="website.layout"><t t-set="pageName" t-value="'x'"/>...body...</t>`.
- New: pass values as attributes: `<t t-call="website.layout" pageName="'x'">...body...</t>`.
  Also `name.f="format {{x}}"` for format strings and `name.translate="Text"` for translatable
  literals.
- The body itself (`0`) still passes. Only `t-set`s used by the callee must move.
- `upgrade_code` `19.1-00-t-call` does most of it. It skips t-calls inside `<kanban>` and t-calls
  with non-`t-` attributes, and logs what it skipped, so fix those by hand.

## Reports

- `ir.actions.report` records: the `report_file` field is removed in 20; delete it.
  `report_name`, `report_type`, `binding_model_id`, `print_report_name` and `paperformat_id` are
  unchanged.
- `<report>` shortcut tag: removed in 17. Use `<record model="ir.actions.report">`.
- Layouts removed in 20: `web.external_layout_bold`, `web.external_layout_boxed`,
  `web.external_layout_striped` (14's `_background` and `_clean` earlier).
  - Kept: `web.external_layout_standard`, `bubble`, `folder`, `wave`.
  - New: `center`, `compact`, `dual`, `lines`.
  - An `inherit_id` on a removed layout blocks install; retarget to `web.external_layout_standard`
    or the layout-independent `web.external_layout`.
- `web.html_container`, `web.external_layout`, `web.internal_layout` and `web.basic_layout` still
  exist.
- Font Awesome icons in reports (`fa fa-check`) no longer render (see scss-bootstrap-icons.md).

## Mail templates (`mail.template` records)

| Source | Odoo 20 |
|---|---|
| 14 Jinja/Mako `${object.name}` in `body_html` | QWeb: `<t t-out="object.name"/>` in `body_html` (`render_engine` qweb) |
| 14 `${object.name}` in `subject`, `email_to`, `partner_to` | inline_template: `{{ object.name }}` |
| `% if cond:` … `% endif` blocks | `<t t-if="cond">…</t>` |
| `report_template` field | `report_template_ids` (`[(4, ref('x'))]`) |
| `t-esc` inside `body_html` | `t-out` (same silent-blank rule) |

`${` is rendered literally in 15+, so the email shows `${object.name}`.
