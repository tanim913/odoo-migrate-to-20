# Field and model renames (14 to 20)

A renamed or removed field used in a view or data file blocks install ("Field x does not exist").
Used in Python it is a runtime error. Used in JS it shows as undefined.

These renames touch Python, XML and JS at once, so do them **globally first**, before fanning out
per area. Always confirm the field in 20:
`grep -n "<field> = fields" $ODOO20_SERVER/addons/<mod>/models/*.py`.

| Since | Model | Old | New in 20 |
|---|---|---|---|
| 15 | `stock.picking` | `move_lines` | `move_ids` |
| 16 | `account.move.line` | `analytic_account_id`, `analytic_tag_ids` | `analytic_distribution` (JSON `{account_id: pct}`) |
| 16 | `account.move.line` | `exclude_from_invoice_tab` | removed (`display_type`) |
| 17 | `stock.move` | `quantity_done` | `quantity` (+ `picked`) |
| 17 | `stock.move.line` | `qty_done` | `quantity` (+ `picked`) |
| 17 | `stock.move` | `reserved_availability` | removed (`quantity`) |
| 17 | `stock.picking` | `immediate_transfer` | removed |
| 17 | `hr.employee` | `address_home_id` | `private_street`, `private_city`, `private_email`, … |
| 17 | `mail.template` | `report_template` | `report_template_ids` |
| 18 | `product.template` | `detailed_type` | `type` (`consu`/`service`/`combo`) + `is_storable` boolean |
| 18 | `ir.cron` | `numbercall`, `doall` | removed; delete from XML |
| 18 | `res.partner` | `title` | removed |
| 19 | `res.users`, `ir.ui.view`, `ir.ui.menu`, `ir.actions.*` | `groups_id` | `group_ids` |
| 19 | `res.groups` | `users` | `user_ids` |
| 19 | `res.groups` | `category_id` | `privilege_id` → a `res.groups.privilege` record that has `category_id` |
| 19 | `res.partner` | `mobile` | removed (use `phone`) |
| 19 | `uom.uom` | `category_id`, `factor_inv`, `uom_type` | `relative_factor`, `relative_uom_id` |
| 19 | `product.template` | `uom_po_id`, `packaging_ids` | removed |
| 19 | `sale.order.line` | `tax_id`, `product_uom` | `tax_ids`, `product_uom_id` |
| 19 | `purchase.order.line` | `taxes_id`, `product_uom` | `tax_ids`, `product_uom_id` |
| 19 | `hr.contract` model | – | `hr.version` |
| **20** | `stock.move`, `stock.move.line` | `product_uom`, `product_uom_id` | **`uom_id`** |
| **20** | `res.partner` | `company_type` | removed (`is_company`) |
| **20** | `uom.uom` | `rounding` | removed |
| **20** | `account.move` | `checked` | `review_state` |
| **20** | `ir.actions.report` | `report_file` | removed; delete the field line |
| **20** | `website.page` | `date_publish` | removed |
| **20** | `sale.order` | `shop_warning` | removed (`_add_warning_alert`) |

## How to find more

When install fails with `Field "x" does not exist in model "y"`, find where it went. A shallow clone
has no history, so compare the trees directly:

```bash
grep -rn "\bx = fields" <older Odoo checkout>/addons/<mod>/models/   # what it was (see MIG20_OLD_SOURCES)
grep -rn "string=\"<its label>\"" $ODOO20_SERVER/addons/<mod>/models/   # same label, new name?
```

Record every new rename found in `lessons-learned.md`.

## Data implications

Code migration does not migrate data. When a module's **own** stored field is renamed during the
migration, note in `MIGRATION_20.md` that existing databases need a `migrations/20.0.x.y.z/`
pre-migrate script (`ALTER TABLE ... RENAME COLUMN`). Standard fields are migrated by Odoo's upgrade
service.
