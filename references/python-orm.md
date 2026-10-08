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
| 20 | `@tools.ormcache(...)`, `tools.cache` | `@api.ormcache(...)` (`from odoo.api import ormcache`); the old name still works but warns at load | W |
| 20 | `env.clear()` | `env.transaction.clear()` (or `env.transaction.reset()`) | W |
| 20 | `from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY`; `if err.pgcode not in ...` | `from odoo.sql_db import PG_CONCURRENCY_EXCEPTIONS_TO_RETRY`; `if not isinstance(err, PG_CONCURRENCY_EXCEPTIONS_TO_RETRY)` | B |
| 20 | `@classmethod def _login(cls, db, login, password, user_agent_env)` returning the uid | `def _login(self, credential, user_agent_env)` returning auth info (`{'uid': ...}`); call `super()._login(credential, user_agent_env)`. A check that must log even when the login is refused keeps its own cursor: `with self.env.registry.cursor() as cr:` (was `cls.pool.cursor()`) | R |
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


### Check the model before changing a detected signature

The scanner's method-name index can match a helper on a new custom model to an
unrelated core/enterprise model. Resolve _name/_inherit and the defining model
first. A matching name alone is not an override; document a false positive rather
than changing a custom public contract to match an unrelated method.


### Payment providers and transactions (Odoo 20 payment engine)

Check each point in `addons/payment/models/payment_transaction.py`, `payment_data.py` and the
provider's own module (e.g. `payment_authorize`) before porting a payment customisation.

| Odoo 17 | Odoo 20 |
|---|---|
| `payment.provider.state` (`disabled` / `test` / `enabled`) | removed: `active` (False = disabled) and `is_live` (False = test). `AuthorizeAPI` and similar helpers keep `self.is_live`, not `self.state` |
| `tx._handle_notification_data(code, data)`, processed at once | `tx._record(payment_data)`: stores a `payment.data` row and triggers `payment.processing_cron`; processing (`_apply_updates`, amount check, `_tokenize`) and post-processing run **later, in another transaction**. Code that read `tx.state` right after the call now reads the old state |
| `_process_notification_data`, `_get_tx_from_notification_data` | `_apply_updates(payment_data)`, `_extract_reference(provider_code, payment_data)`, `_extract_amount_data(payment_data)` |
| `_cron_finalize_post_processing`, `_finalize_post_processing` | `_cron_post_process`, `_post_process`; `tx._try_post_process()` post-processes immediately (savepoint, falls back to the cron) |
| capture/void/refund on the transaction itself (`_send_capture_request` used `self.provider_reference`) | `tx._capture(amount)` / `_void()` / `_refund()` create a **child transaction** and call `child._send_*_request()`, which must use `self.source_transaction_id.provider_reference`. A void child of a payment ends `cancel`, not `done` |
| writing fields on `payment.transaction` freely | `write()` raises unless the context has `payment_safe_write=True` (what the processing uses) |
| `_set_done(state_message)` etc. positional | keyword-only: `_set_done(state_message=...)`; `_set_error(state_message)` unchanged |
| provider-specific tokenize (e.g. `_authorize_tokenize`) | `_tokenize(payment_data)` + `_extract_token_values(payment_data)` |
| `payment.method._get_compatible_payment_methods`, `payment.provider._get_compatible_providers` | `payment.provider._find_available_payment_methods`, `_find_available_providers`, `_find_available_tokens` |

Backend flows that need the result immediately (a wizard that charges and then shows the outcome)
can reproduce what `payment.data._cron_process` does for one transaction: `_record`, lock the
transaction (and its source) and the pending `payment.data`, `_process(payload)` with
`payment_safe_write=True`, delete the row, then `_try_post_process()`, all in a savepoint so the
data stay queued for the cron if anything fails. Portal and webhook flows keep `_record` alone.
