# Security to Odoo 20 (`ir.access` replaces ACLs and record rules)

## What changed (install blocker)

- **Odoo 20 has no `ir.model.access` and no `ir.rule` model.** One model, `ir.access`
  (`odoo/addons/base/models/ir_access.py`), holds both.
- A leftover `ir.model.access.csv` fails, because the CSV model is taken from the file name. XML
  `<record model="ir.rule">` records fail the same way.
- Access is **default deny**. Every model the module defines needs at least one row.

`security/ir.access.csv`:

```csv
id,name,model_id,group_id/id,operation,domain
access_property_user,property user,bay.vista.property,base.group_user,crud,
access_property_public,property public read,bay.vista.property,base.group_everyone,r,"[('website_published', '=', True)]"
rule_property_company,property multi-company,bay.vista.property,,crud,"[('company_id', 'in', company_ids + [False])]"
```

- `model_id` is the **model name** (`sale.order`), not `model_sale_order`.
- `operation` is a subset of `crud`.
- `domain` empty means all records. Its eval context: `user`, `time`, `company_ids`, `company_id`.
- A row **with** a group grants: rows for the same group are OR-ed.
- A row **without** a group is a restriction AND-ed for everybody. This is how a global `ir.rule`
  (multi-company) becomes one row.
- Grant to everyone, including public/portal: `base.group_everyone`. Internal users:
  `base.group_user`. Portal: `base.group_portal`. Public: `base.group_public`.

## Converting

1. `run_upgrade_code.sh` runs `19.4-00-ir-access` with core on the path, so implied groups resolve.
2. Review every WARNING/ERROR it printed. Common ones:
   - An old ACL row with an empty `group_id` gave access to **everyone, including public users**.
     The script maps it to `base.group_everyone` with the same permissions.
     - If the model is internal-only data, **narrow it to `base.group_user`** (or the module's
       groups) instead of keeping public write access.
     - Keep `base.group_everyone` only where the website/portal really reads it, and give those
       rows only `r` plus a published/ownership domain.
     - Record the decision in the report.
   - Rules without a group become group-less restriction rows. Check the domain still makes sense
     as an AND restriction.
   - Rules with `perm_*` flags map to `operation` letters. Check the letters.
3. Delete any leftover `ir.model.access.csv` / `ir.rule` records and make sure the manifest lists
   `security/ir.access.csv` after the group XML.

## Groups (19+)

- `res.groups.category_id` no longer exists. Groups hang from a **privilege**
  (`res.groups.privilege`, fields `name`, `category_id`, `sequence`, `description`). The privilege
  hangs from an `ir.module.category`.
- `users` → `user_ids` on res.groups.
- `groups_id` → `group_ids` on res.users, views, menus and actions.

Old:

```xml
<record id="module_category_x" model="ir.module.category"><field name="name">X</field></record>
<record id="group_x_admin" model="res.groups">
    <field name="name">Admin</field>
    <field name="category_id" ref="module_category_x"/>
    <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
    <field name="users" eval="[(4, ref('base.user_admin'))]"/>
</record>
```

Odoo 20 (pattern from `odoo/addons/base/security/base_groups.xml`):

```xml
<record id="module_category_x" model="ir.module.category"><field name="name">X</field></record>
<record id="res_groups_privilege_x" model="res.groups.privilege">
    <field name="name">X</field>
    <field name="category_id" ref="module_category_x"/>
</record>
<record id="group_x_admin" model="res.groups">
    <field name="name">Admin</field>
    <field name="privilege_id" ref="res_groups_privilege_x"/>
    <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
    <field name="user_ids" eval="[(4, ref('base.user_admin'))]"/>
</record>
```

## Also check

- `groups="..."` attributes in views, fields and menus: every group xmlid must exist in 20.
  Grep for it in core and enterprise.
- `sudo()` in public controllers: keep it minimal, and never trust request params in domains.
  Run the `odoo-security` skill checklist on controllers.
