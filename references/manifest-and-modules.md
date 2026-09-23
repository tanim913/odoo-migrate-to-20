# Manifest and module dependencies

## Version (install blocker, silent)

`odoo/modules/module.py`: a version with 2 or 3 parts gets `20.0.` prepended. A version with 4 or 5
parts must start with `20.`. Otherwise the module is logged as "incompatible version, setting
installable=False" and **silently disappears** from Apps.

Rule: set `'version': '20.0.<x>.<y>.<z>'`.
- Keep the source's module-level part: `17.0.1.2.0` becomes `20.0.1.2.0`, and `'1.3'` becomes
  `'20.0.1.3.0'`.
- Bump the last part when data migration scripts are added.

## Keys

| Key | Status in 20 | Action |
|---|---|---|
| `qweb` | ignored (since 15), templates never load | move each file into `assets` → `web.assets_backend` (backend) or `web.assets_frontend` (website) |
| `demo_xml`, `init_xml`, `update_xml` | ignored | move into `data` / `demo` |
| `license` | missing gives a warning, defaults to LGPL-3 | keep the source's; add `'LGPL-3'` if missing |
| `installable: False` | honoured | set `True` only after the module really works |
| `assets` | required for all JS/SCSS/owl XML | see backend-js-owl3.md and website-interactions.md for bundle names |
| `external_dependencies` | `{'python': [...]}` checked at install | `pytz` and `xlwt` are **no longer** in Odoo's requirements; install them (`$ODOO20_PYTHON -m pip install pytz`) and list them in `external_dependencies`, or port to `zoneinfo` / `xlsxwriter` |

`data` order still matters:
- security first (`security/*.xml` groups before `security/ir.access.csv`)
- then data, views, menus last
- `upgrade_code`'s ir-access script appends `ir.access.csv` at the end of `data`, which is fine for
  install. If a view or menu references a group created in the same module, the group XML must come
  before them.

Every file in `data`/`demo`/`assets` must exist on disk.

## Removed or merged modules (a `depends` on these blocks install)

Before trusting this table, confirm with
`ls $ODOO20_SERVER/addons/<m> $ODOO20_ENTERPRISE/<m>`.

| Removed module | Use in 20 |
|---|---|
| `website_sale_wishlist`, `website_sale_comparison`, `website_sale_comparison_wishlist`, `website_sale_stock_wishlist` | `website_sale` |
| `website_sale_delivery` (17), `website_sale_product_configurator` (18), `website_sale_picking` (18) | `website_sale` |
| `website_sale_autocomplete`, `website_sale_mondialrelay` | drop |
| `sale_product_configurator` | `sale` |
| `website_form` (15) | `website` |
| `web_editor` (19) | `html_editor` (fields/editor) + `html_builder` (website builder) |
| `base_vat`, `base_iban` | `account` |
| `stock_picking_batch` | `stock` |
| `hr_contract` | `hr` (model `hr.version`) |
| `hr_org_chart`, `hr_hourly_cost` | `hr` |
| `hr_work_entry_holidays` | `hr_work_entry` |
| `coupon`, `sale_coupon`, `sale_gift_card`, `website_sale_coupon` | `loyalty`, `sale_loyalty`, `website_sale_loyalty` |
| `note`, `pad`, `fetchmail`, `membership`, `transifex`, `website_twitter`, `website_jitsi` | drop (note: `project_todo`) |
| `payment_ogone/alipay/sips/payulatam/payumoney/test/transfer` | `payment_custom` (wire transfer), `payment_demo` |
| `account_edi_facturx`, `account_edi_ubl` | `account_edi_ubl_cii` |
| `web_kanban_gauge`, `procurement_jit` | drop |
| `iot_base` (ent) | `iot` |
| enterprise `industry_fsm*`, `helpdesk_fsm*` | check `planning_field_service*` |
| enterprise `hr_contract_*`, `hr_payroll_holidays`, `stock_barcode_picking_batch`, `account_accountant_batch_payment` | check the merged parent |

When a depended-on module was merged, also check that the xmlids the module references still exist
under the new module name. `website_sale_wishlist.xyz` becomes `website_sale.xyz` only if the record
moved with its id, so grep before renaming.

## Custom dependencies

A `depends` on another custom module means that module must be migrated first, into the same
`$MIG20_TARGET_ROOT/<project>/`. Resolve the dependency order (topological) and migrate
bottom-up. A third-party module (Cybrosys, Emipro, Droggol, printnode, queue_job, …) usually has a
20 release upstream. Prefer asking the user to fetch it over migrating a vendor module.
