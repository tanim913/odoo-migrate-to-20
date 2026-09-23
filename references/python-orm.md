# Python / ORM to Odoo 20

Legend:
- **B** = install/import blocker
- **S** = silent (override never called, constraint vanishes, wrong output)
- **R** = runtime error
- **W** = warning only
- **UC** = fixed by upgrade_code

Before using any API, confirm it exists in 20:
`grep -rn "def <name>" $ODOO20_SERVER/odoo/orm $ODOO20_SERVER/odoo/models $ODOO20_SERVER/addons/<module>`.
Model code lives in `odoo/orm/` (`models.py`, `fields.py`, `decorators.py`, `environments.py`),
and `odoo/models/__init__.py` re-exports it.

| Since | Old | Odoo 20 | Kind |
|---|---|---|---|
| 13 | `@api.multi`, `@api.one` | delete (methods are multi by default) | B |
| 19 | `@api.returns(...)` | delete | B |
| 19 | `@api.model` + `def create(self, vals)` | `@api.model_create_multi` + `def create(self, vals_list)`; loop the list; `super().create(vals_list)` | R (20 auto-wraps and passes a list) |
| 16 | `fields_view_get` | `_get_view(view_id, view_type, **options)` returning `(arch, view)`, or `get_views` | S |
| 17 | `def name_get(self)` | `_compute_display_name(self)` setting `rec.display_name`; add `@api.depends(...)` | S |
| 17 | `_name_search(...)` | `_search_display_name(self, operator, value)` returning a domain, or `_rec_names_search = ("name", "ref")` | S |
| 19 | `_sql_constraints = [(n, "unique(x)", msg)]` | `_n = models.Constraint("UNIQUE(x)", "msg")`; indexes `models.Index("(x)")` / `models.UniqueIndex("(x)")` | S, UC |
| 17 | field `states={...}` | remove; express in view `readonly="state != 'draft'"` | S |
| any | field `track_visibility=` | `tracking=True` | S |
| 20 | field `group_operator=` | `aggregator=` | S |
| any | `digits_compute=` | `digits='Product Price'` | S |
| 18 | `ir.property` model / `company_dependent` storage | company_dependent fields are jsonb; never read `ir.property` | R |
| 18 | `self.user_has_groups("a,b")` | `self.env.user.has_groups("a,b")` / `has_group("a")` | R |
| 20 | `check_access_rights(op)` / `check_access_rule(op)` / `_filter_access_rules(op)` | `check_access(op)` / `has_access(op)` / `_filtered_access(op)` | R |
| 19 | `self._cr`, `self._uid`, `self._context` | `self.env.cr`, `self.env.uid`, `self.env.context` | W, UC |
| 20 | `from odoo.osv import expression`; `expression.AND/OR/normalize_domain`, `expression.TRUE_DOMAIN` | `from odoo.fields import Domain`: `Domain.AND([...])`, `Domain.OR([...])`, `Domain(dom)`, `Domain.TRUE`; a Domain works wherever a list domain did | B |
| 20 | `read_group(domain, fields, groupby, lazy=...)` returning dicts | `_read_group(domain, groupby=[...], aggregates=["amount:sum"])` returns tuples; `formatted_read_group(...)` returns dicts; the public `read_group` now has a different signature | R |
| 20 | `from odoo.tools import ormcache_context`, `ormcache(skiparg=)` | `from odoo.api import ormcache` (keys must include what varied) | B |
| 20 | `self.env.registry.clear_cache()` / `clear_caches()` | `self.env.transaction.invalidate_ormcache()` | R, UC partial |
| 20 | `toggle_active()` | `action_archive()` / `action_unarchive()` | R |
| 20 | `_check_recursion()` | `_has_cycle()` (negated meaning: True when a cycle exists) | R |
| 20 | `odoo.tools.lazy_property` | `functools.cached_property` | B |
| 20 | `odoo.tools.pycompat`, `ustr()`, `get_encodings` | plain `str`; delete | B |
| 20 | `odoo.tools.query.Query` | `odoo.models.Query` | B |
| 20 | `from odoo.tools import mod10r, street_split` | `from odoo.tools.business_data import ...` | B |
| 20 | `odoo.registry(db)` | `from odoo.modules.registry import Registry; Registry(db)` | R |
| 17 | `message_post_with_view` / `message_post_with_template` | `message_post_with_source(source_ref, render_values=..., subtype_xmlid=...)` | R |
| 20 | mail `_track_subtype(init_values)` | `_track_log_get_default_subtype(...)`; confirm the signature in `addons/mail/models/mail_thread.py` | S |
| 20 | mail `_track_template(changes)` | `_track_template_parameters(tracked_fields)` | S |
| 17/20 | tests `SavepointCase`, `SingleTransactionCase` | `TransactionCase` (setUpClass data is rolled back per class) | B |
| 20 | `import pytz` | `from zoneinfo import ZoneInfo` (core dropped pytz), or add pytz to `external_dependencies` and install it | B if not installed |
| 20 | `import xlwt` | `xlsxwriter` | B |
| py3.12 | `imp`, `distutils`, `pkg_resources` | `importlib`, `shutil`/`sysconfig`, `importlib.metadata` | B |
| – | `lxml.html.clean` | package `lxml-html-clean` (`from lxml_html_clean import Cleaner`) | B |
| – | `PyPDF2` | `odoo.tools.pdf` helpers or `pypdf` | B on py3.13 |

Model and field renames are in field-model-renames.md.

## Writing style for rewritten code

- `self.env._("text %s", x)` is preferred for translations in 18+; `_` from `odoo` still works.
  Only translate static literals.
- Batch ORM calls outside loops: `create(vals_list)`, `search` once, and `mapped`/`filtered` on
  the recordset.
- Keep the source module's structure. Migration is not refactoring. Fix only what 20 requires, and
  fix it the way current core code does it.
