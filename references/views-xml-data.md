# XML views, actions and data records to Odoo 20

Every inherited view's xpath must resolve against the **20** parent view, and every `inherit_id` or
`ref` must exist in 20. A broken xpath blocks install ("Element … cannot be located in parent
view"). To check:

```bash
grep -rn 'id="<xmlid-suffix>"' $ODOO20_SERVER/addons/<mod>/ $ODOO20_ENTERPRISE/<mod>/
```

Then open the 20 parent arch and rewrite the xpath on **names** (`//field[@name='x']`), never on
position.

| Since | Old | Odoo 20 | Kind / fix |
|---|---|---|---|
| 17 | `attrs="{'invisible': [('state','=','done')]}"` | `invisible="state == 'done'"` (Python expression; `and`/`or`/`not`, `in`, `parent.x`, `context.get('x')`); likewise `readonly=`, `required=`, `column_invisible=` (list columns) | **B** (ValidationError "Since 17.0…"), manual |
| 17 | `states="draft,sent"` on buttons/fields | `invisible="state not in ('draft', 'sent')"` | B, manual |
| 17 | `<report .../>`, `<act_window .../>` data tags | `<record model="ir.actions.report">` / `<record model="ir.actions.act_window">` | B, manual |
| 17 | settings `<div class="app_settings_block" data-key="x">` layout | `<app string=".." name="x"><block title=".."><setting string=".." help=".."><field name="y"/></setting></block></app>` | visual, manual |
| 18 | `<tree>`, `view_mode="tree,form"`, `tree_view_ref` | `<list>`, `view_mode="list,form"`, `list_view_ref` | B, UC |
| 18 | `<div class="oe_chatter"><field name="message_follower_ids"/>...</div>` | `<chatter/>` (options: `<chatter reload_on_follower="True"/>`) | S (chatter vanishes), manual |
| 18/19 | kanban `<t t-name="kanban-box">`, `kanban_image()` / `kanban_getcolor` helpers | `<t t-name="card">` with `<field name="x" widget="image"/>` etc.; `kanban-menu` is still valid | B in 19+, manual; copy a 20 kanban arch (e.g. `addons/project/views/project_project_views.xml`) |
| 18 | `ir.cron` `numbercall`, `doall` | delete the fields; `interval_number`/`interval_type` stay | B |
| 18 | cron `<field name="code">model.method()</field>` | unchanged; `state=code` default | – |
| 19 | `groups_id` on views/menus/actions/users (XML `<field name="groups_id" eval=...>`) | `group_ids` (`<menuitem groups="..."/>` attribute is unchanged) | B |
| 19 | `res.groups` `category_id` | `privilege_id` referencing a `res.groups.privilege` record (see security-ir-access.md) | B |
| 19 | `res.groups` `users` | `user_ids` | B |
| 20 | `type="base64" file="..."` | `type="bytes"` | W, UC |
| 20 | `ir.actions.report` `report_file` | delete the field | B |
| 20 | `widget="remaining_days"` / `"selection_badge"` | `relative_date` / `badges_selection` | R (field falls back / errors) |
| 20 | button `icon="fa-check"` | Material Symbols name `icon="check"`; check the name is in `$ODOO20_SERVER/addons/web/tooling/icons/icons_wishlist.txt` | visual |
| 20 | `<i class="fa fa-x"/>` in arch | `<i class="oi" data-icon="name"/>` (see scss-bootstrap-icons.md) | visual |
| 19 | `<asset>` data tag | `<asset id=".." name=".." ><bundle>web.assets_frontend</bundle><path>mod/static/..</path></asset>` shortcut for `ir.asset` (old `ir.asset` records still work) | – |

## Domain and context expressions

- Domains in XML are evaluated client-side and server-side the same way as before.
- `context_today()` still works. `upgrade_code` 18.5 optionally rewrites it to `'today -1m'` syntax.
- `uid` and `user` are available in domains, and `company_ids`/`company_id` in rule domains.

## Search views

- `<filter date="field"/>` and `<searchpanel>` are unchanged.
- **20 RNG rejects attributes on `<group>` inside `<search>`**: `<group string="Filters">` and
  `<group expand="0" string="Group By">` fail install ("Invalid attribute string for element
  group"). Drop the attributes (`<group>`) or drop the wrapper. Consecutive filters are OR-ed,
  and `<separator/>` splits AND groups.

## Menus and actions

- An action window with `view_mode` containing `tree` breaks the menu at runtime. UC fixes the
  string, but check actions defined in Python too (`'view_mode': 'tree,form'` becomes
  `'list,form'`, `'views': [(False, 'tree')]` becomes `'list'`).
- `ir.actions.act_window` `view_type` field: removed since 13; delete it if present.
