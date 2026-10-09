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
| **20** | `res.partner` | `company_type` | removed (`is_company`); `default_company_type` in contexts too. A `<field name="company_type"/>` in a view stops the install |
| **20** | `res.partner` | `team_id`, `company_name`, `sla_ids` (helpdesk), `property_payment_method_id` (account_check_printing), `mobile_blacklisted` | removed; `commercial_company_name` is a stored related field. A module that still needs one defines the field itself (and keeps the column in the data upgrade) |
| **19** | `res.partner.title` | model and `res.partner.title` field | removed from core. A module that shows or edits titles declares `_name = 'res.partner.title'` and the `title` Many2one again (same names keep the table and column of an upgraded database); the 5 default titles are gone too (scan `partner-title`) |
| **20** | `res.country` | `zip_required` | `zip_applicability` (`'required'`, `'optional'`, `'not_applicable'`) (scan `country-zip-required`) |
| **20** | `res.partner` | `can_edit_vat()` | `not _has_confirmed_documents()` |
| **20** | `website` | `get_current_website()` | `self.env.website` (from the request context; in the back office fall back to the company's website) |
| **20** | `product.template` | `categ_id` required (default "All") | optional: a domain `('categ_id.name', '!=', X)` now also drops products without a category; add `'|', ('categ_id', '=', False)` |
| **20** | `res.partner` method | `action_view_sale_order` | removed: the Sales smart button is `type="action" name="sale.act_res_partner_2_sale_order"` |
| **20** | `sale.subscription.pricing` model | `product_template_id`, `product_variant_ids`, `price`, `plan_id`, `pricelist_id` | merged into `product.pricelist.item`: rules with a `plan_id` (`product.template.subscription_rule_ids`), `product_tmpl_id`, `product_id`, `fixed_price`. `pricelist_id` gets a default pricelist on create: pass `pricelist_id: False` for a rule that applies to every pricelist |
| **20** | `account.move.send` | several invoices in one wizard (`mode != 'invoice_single'`) | `account.move.send.batch.wizard` (`move_ids`; the helpers `_get_default_mail_template_id`, `_get_default_mail_partner_ids` are on the shared abstract `account.move.send`) |
| **20** | `choose.delivery.carrier` method | `_get_shipment_rate` | `_set_delivery_vals(delivery_vals)` sets the wizard prices |
| **20** | `res.users` / `res.partner` | `signup_url` | removed: `user.partner_id._get_signup_url()` (after `signup_prepare(signup_type)`, which lost its `expiration` argument). scan `signup-url` |
| **20** | default groups of new users | record `base.default_user` (a template user whose groups were copied) | group `base.default_user_group`: add the groups to its `implied_ids` (`<record id="base.default_user_group" model="res.groups"><field name="implied_ids" eval="[(4, ref('x.group'))]"/></record>`), read by `res.users._default_groups()` |
| **20** | mail template | `portal.mail_template_data_portal_welcome` (object `portal.wizard.user`) | `auth_signup.portal_set_password_email` (object `res.users`): `object.user_id.X` becomes `object.X` |
| **20** | `sale.order` | `require_payment` | removed: an order needs an online payment when `prepayment_percent > 0` |
| **20** | `sale.subscription.plan` | `billing_period_unit` | a unit added by a module (e.g. `day`) needs its own `_compute_billing_period_display` / `_compute_delivery_period_display`: the 20 computes raise on unknown units |
| **20** | decimal precision | `'Product Unit of Measure'` | `'Product Unit'` (`digits='Product Unit'`). scan `precision-uom` |
| **20** | `mail.message` tracking | `tracking_value_ids` / `mail.tracking.value` | gone from the message; tracking values are written at commit time (`mail.track.mixin`). In a rollback-only test check `record._track_get_fields()` instead of the message |
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
