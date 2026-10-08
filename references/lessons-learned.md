# Lessons learned

Append a dated entry after every migration that teaches something the other references don't
already say. Keep each lesson general: what went wrong, the rule that prevents it, and how it was
detected. If `scan.py` could have caught it, add a rule there too.

## From a real 16→19 eCommerce migration (website_sale customisations)

- **Never comment out code or assets to make a module install.** In that migration 3 of 5 JS files
  were dropped from the manifest and cart/xpath inherits were commented out, so features silently
  died. If something can't be migrated now, list it in `MIGRATION_20.md` under "Not migrated" with
  the reason, so it stays visible.
- **Half-migrated JS is worse than none.** The 19 result still used publicWidget and jQuery, and
  none of it survives 20. Migrate JS all the way to the target version's pattern.
- **Re-diff template overrides against the target version.** `h6.o_wsale_products_item_title`
  became `h2`; the cart table became divs; custom forms lacked `oe_website_sale`, so the core JS
  never bound.
- **Carry core classes and ids into overriding templates.** About 30 responsive regressions came
  from custom shop templates dropping `o_wsale_has_sidebar`, `o_wsale_uses_grid_design`, etc.
- **Check that routes posted by custom forms still exist with the same `type`.** A custom form kept
  posting to `/shop/cart/update`, which became jsonrpc in 19.
- **Deprecated-but-working patterns become removed.** `t-esc`, `fa fa-`, `data-toggle` and
  `type='json'` were harmless in 19; in 20 they render blank, show broken icons, or warn. Always
  migrate deprecations, not only errors.

## Tooling

- `upgrade_code --from X` with core addons on the path crashes in the l10n scripts, and through
  `odoo-bin` it would rewrite core. Run per script, standalone, module only (ir-access with core +
  `--glob`). `scripts/run_upgrade_code.sh` does this.
- The owl3 script imports `useRef` etc. from `@web/owl2/utils`, which doesn't export them. `scan.py`
  flags this as a BLOCKER after the automatic pass.
- Odoo's HttpCase browser tests are **skipped, not failed**, when `websocket-client` or Chrome is
  missing. "0 failed of N tests" can mean nothing ran, so run `doctor.sh` first and check the log
  for "Open ... in browser".

## 2026-09-23: 18→20 real-estate module (website pages, Owl map widget, systray chatbot, mail hook)

- **Override signatures change silently.** `mail.thread._message_post_after_hook(message, msg_vals)`
  lost `msg_vals` in 20. An override with the old signature crashes every chatter post. `scan.py`
  now compares every override of a core method with its 20 signature (`override-signature`).
- **External xmlids get renamed.**
  - `website.default_website` is now `base.default_website`.
  - `project_todo.project_task_preload_action_todo` is now `project_task_action_todo`.

  `scan.py` now checks every external xmlid a module references (`xmlid-missing`).
- **Third-party Python libraries are not in the new venv** (geopy, openai…). `scan.py` checks
  importability (`py-missing-lib`). Install them into the Odoo 20 venv and declare them in
  `external_dependencies`.
- **Search view `<group string="...">` is rejected by the 20 RNG.** `scan.py` rule
  `xml-search-group-string`.
- **Kanban card classes are `o_card_*`, not `o_kanban_*`.** Copy the aside/main structure from a 20
  core kanban (e.g. hr employee).
- **ACL rows without a group meant "everyone, including public".** Keeping that as
  `base.group_everyone` crud grants public write access. When routes are `auth='user'` and use
  `sudo()`, narrow the rows to internal crud + portal read, and record the decision.
- **Secrets in source.** An API key was found in a code comment. Remove it from the migrated copy
  and tell the user to revoke it (it is still in the original).
- **Systray replacement templates moved.** `mail.MessagingMenu` is no longer the systray item in 20
  (`mail.MessagingMenuInDropdown` is). Overriding the wrong one breaks Discuss.

## 2026-09-23: 16→20 fork of enterprise `social` (legacy + Owl 1 JS, attrs, tests)

- **Detect forks before porting.** The module was upstream `social` 16, renamed, with a tiny delta.
  A line-by-line port would have meant rewriting about 120 blockers. Rebasing onto upstream
  `social` 20 (`fork_check.py` + `rebase_fork.py`) installed cleanly on the first try, and the
  renamed upstream tests passed.
- **Rename module references, never model names.** xmlids, template names, groups, asset paths,
  `@module/` imports and `odoo.addons.module` all get the new name. `social.media`-style model
  names keep the old prefix, so the schema is unchanged.
- **Licences travel with code.** The fork claimed LGPL-3 on proprietary enterprise code; the rebased
  module keeps the upstream licence and the report flags it.
- **Control runs separate migration bugs from upstream behaviour.** The clickbot timed out opening a
  kanban card that opens a list, not a form. The same smoke test on upstream `social` 20 failed
  identically.
- **Identity-checked methods.** Odoo 20 added `@check_identity` to methods such as
  `change.password.user.change_password_button`. Called from code they return a popup action and do
  nothing, so user creation silently produced accounts without passwords. `scan.py` rule
  `identity-checked-call`. Verify key create flows in a shell, not only through the UI smoke test.
- **Signature comparison must ignore keyword-only and positional-only markers.** Core defs use
  `(self, /, *, a, b)`; compare only the positional parameters.

## 2026-09-24: tours, tests and import resolution (checked on 14, 16 and 19 modules and on 20 core)

- **Tours break in four quiet ways on 20.** A strict schema rejects old step keys (`extra_trigger`,
  `position`, `edition`, empty `run` functions). Steps without `run` no longer click (since 18).
  `run: "text x"` is gone. And a test tour now starts where `start_tour()` opens, not at its
  registered `url` (that redirect ended in 20). `scan.py` area `tests` covers all four; the old
  16 modules had 30+ such findings each and none showed up as an install error.
- **Resolve imports instead of listing moved names.** Real-importing every `odoo.*` import on 20
  found `Form` no longer in `odoo.tests.common`, `odoo.osv`, `check_method_name`, and enterprise
  classes renamed from `SocialAccountFacebook` to `SocialAccount`. Those last imports sat in
  `try/except ImportError`, so on 20 the fallback branch would always run and the tests' external-API
  mocks would silently never apply. Resolving JS imports found missing files (`@mail/model/*`,
  `@web/views/kanban/kanban_model`) and missing names (`useState`/`useRef` from `@odoo/owl`).
  - `@odoo/owl` exports come from `owl.js` **plus** the Owl 2 compatibility layer
    (`web/static/src/owl2/*.js`, `owl.X = ...`).
  - `@odoo/hoot*` resolve through `@odoo-module alias=` headers.
- **Check the checker on core.** Running the new checks over 20 core modules first caught three
  false positives before any user saw them: helper-call arguments treated as steps, `:image`
  inside `[src^='data:image']`, and the Owl compat names. Do this for every new scanner rule.
- **Screenshots beat logs for browser failures.** The first flow tour failed on step 1; the failure
  screenshot showed the home menu at once (the tour `url` redirect is gone). The second showed the
  form filled but "Property For" empty: selection fields are a `SelectMenu` in 20, not a `<select>`.
- **One grep per method is too slow.** The override-signature check ran one grep over all of core
  per method, which took minutes on large modules. One indexed grep of every core `def` brought a
  full scan down to 3–6 s.

## 2026-10-06: 17→20 multi-module portal/website project (26 interdependent modules)

- **The source code may not install on an empty database at all.** Modules installed one by one
  over years can point at each other in ways only an incremental history tolerates:
  - xmlids of modules that are not in `depends` (a menu using another module's action, a view
    using another module's group or `%(record)d`), including circles (A depends on B while B's
    views reference A);
  - core modules used but not declared (models `_inherit`ed or views inherited from loyalty,
    purchase, survey, product_expiry, …);
  - load order inside one module (a view uses a field that a later view of the same file adds;
    one data file's xpath targets markup another file loaded earlier removes);
  - demo data that fails (a demo user whose password breaks another module's policy, a demo file
    listed in the manifest that does not exist).

  Check this **before** migrating: try a fresh install of the source on its own version. Every
  problem found must be fixed in the migrated code (move each cross-reference into the module that
  owns the target, declare real `depends`), or the 20 install test can never pass.
- **Hidden circles also break `-u` on the source version.** When B adds views on top of A's views
  using B's fields, updating A alone fails ("Field … does not exist") because B's models load after
  A. So "it works in production" can mean "it was never updated since".
- **Building a comparison database on the source version** when the code cannot fresh-install:
  1. install all core/enterprise dependencies first (including the undeclared ones) and save that
     database as a template, so retries skip it;
  2. install the custom modules from a temporary patched copy (outside the source tree) with only
     the blocking lines removed or reordered; drop and restore from the template after any failed
     attempt, because a failed install leaves views and data of half-installed modules behind;
  3. re-apply the original code with `-u` on the patched modules only, and load any file that still
     cannot update (see the point above) with `convert_file` from `odoo-bin shell`.
  Record each patch: it is the list of things the migration must fix.
- **Reference-detection regexes need attribute boundaries.** A pattern for `ref="module.xmlid"`
  also matched `t-att-href="appointment.id"` (a QWeb variable), inventing a dependency on the
  enterprise `appointment` module; installing it then broke an unrelated module. Anchor attribute
  names with `(?<![\w-])`.

## 2026-10-06: same project, first batch (OCA queue_job, a login-restriction module, small utilities)

- **A crash in Odoo's converters can pass silently.** `19.4-00-ir-access` reads the manifests and
  security files of every module on the addons path. One sibling module that still depended on a
  removed core module, and one ACL CSV line with 7 columns instead of 8, made it crash, so no
  module got its `ir.access.csv`, while the wrapper still printed OK. `run_upgrade_code.sh` now
  fails with exit code 4 when a script prints a traceback. Fix manifests (removed `depends`) of
  all modules before the automatic pass.
- **The ir-access converter can leave model xmlids** (`module.model_sale_order`, `model_x`) in the
  `model_id` column, where Odoo 20 needs model names (`sale.order`). `run_upgrade_code.sh` now runs
  `fix_ir_access_models.py` after it.
- **Multi-module projects: test from a folder that holds only finished modules.** Sibling modules
  that are not migrated yet log "incompatible version" warnings. `install_test.sh` now ignores
  those for modules outside the tested list, but a folder of symlinks to finished modules
  (`.migration/addons_done/`) is still the cleanest way to install part by part.
- **Vendor modules: look at every newer upstream branch, not only 20.0.** OCA had a 20.0 branch,
  but its module was still `installable: False` with 19 code. The project's copy was identical to
  an old upstream 17 release (diffed against the matching upstream commit), so the module was
  replaced by upstream 19.0 and only 19→20 was ported: far less work, and upstream's own data
  migration scripts (`migrations/18.0.*`, `19.0.*`) come along for the real database upgrade.
  Then compare the feature inventory of the old copy with the new code: features upstream removed
  or redesigned are recorded, and the project is grepped for callers.
- **Scanner false positives fixed:** `identity-checked-call` reported every Python `list.remove()`
  (now `remove`/`enable`/`revoke` count only in an auth context); `override-gone` reported a
  module's own helpers (now methods of new models, methods the module calls itself, including from
  cron/server-action code and `getattr` strings, are skipped). Both checked against real cases
  (an API key `remove()`, removed hooks such as `_message_format`, `_process_notification_data`).

## 2026-10-07: inherited payment forms and ephemeral inputs

- **A clean install can execute zero tests.** Reinstalling an already installed
  test addon with `-i` produced a zero-test clean summary. Explicit `-u` scheduled
  its tests. Require counts, test starts, and browser execution markers; addons
  with only inherited views also need explicit form actions when clickbot has no
  own menu to visit. A DOM-node readiness expression timed out on a visibly
  rendered form; return a boolean. See `tests-and-tours.md`.
- **Read temporary inputs after pending changes, before save/reload.** A button
  context bridge read the focused input too early: backend checks passed while
  real browser payments lacked their card payload. Awaiting `record.isDirty()`
  before collecting nonstored values fixed the input-commit boundary. Keep those
  values in the individual button context and clear them after completion or a
  failed save. See `backend-js-owl3.md`; test the actual browser button/RPC path.


## 2026-10-07: inherited templates, portal XML IDs and access domains

- **XPath hasclass() reads the literal class attribute.** A checkout wrapper
  used only t-attf-class, so a helper that also checked that attribute falsely
  passed a selector that failed Odoo installation. Anchor through a stable named
  child or another literal attribute, and use the actual helper semantics in
  static checks. See website-sale-portal.md.
- **Changing an XML ID's model needs an upgrade step.** A portal home view became
  a portal.entry with the same ID. Fresh installs worked, but an old ir.ui.view
  binding must be retired/remapped before data loading. Keep an inactive legacy
  record for audit where useful; test the migration twice on persisted fixtures
  and include the real module upgrade in production-copy validation.
- **A group domain is a grant in ir.access, not an independent restriction.**
  Keeping a broad internal-user grant beside an own-record group grant did not
  preserve the old group's record restriction: the broader grant won. Review
  the OR of all applicable grants and the AND of global restrictions. Translate
  the complete old rule combination, including administrator exemptions, and
  verify own, unrelated, administrator and public access with actual users.
- **Method-name matches do not establish inheritance.** Signature checks matched
  helpers on a new custom model to similarly named methods on an unrelated
  enterprise model. Verify the defining model and inheritance chain before
  changing signatures; retain explicit dispositions for scanner false positives.
  Field-name regexes also need model context: a custom tax_id is not necessarily
  a renamed sale/purchase line field.

## 2026-10-08: review of a payment and an appointment batch done by another agent

- **Review the other agent's results, not only its summary.** Every check was re-run on fresh
  databases. Two defects had passed its evidence: an SCSS file with `rgb(0 0 0 / 15%)` broke the
  compilation of every bundle that included it (30 warnings in its own browser log, all tests
  green), and a flow script only passed after the browser suite had run first, because its
  constraint patch never applied. New `scan.py` rule `scss-css4-color`, `install_test.sh` now
  fails on bundle compile errors, and `tests-and-tours.md` explains the constraint patch.
- **Migration is not the time to switch features on.** A payment option that was hidden and whose
  posting call was commented out in the source had been made visible ("restoring" a dormant
  path), which added backend raw-card entry. Keep source visibility and behaviour; list such
  options for the user to decide.
- **Payment customisations need the 20 engine map.** Provider `state`, synchronous notification
  handling, capture/void on the source transaction and free writes on transactions are all gone
  (`python-orm.md`, "Payment providers and transactions"). New rules `payment-provider-state`,
  `payment-notification-api`, `payment-finalize-cron`, `payment-compatible-api`; `override-gone`
  now also reports super()-calling overrides of hooks nobody defines (it skipped `_get_*`
  names). An invalid `ir.access` operation (`rc`) stops the install: rule `ir-access-operation`.
- **Scanner false positives fixed:** XML rules matched code inside `<!-- -->` comments (63 `attrs`
  hits in one module were all commented out); `install_test.sh` warnings matched module names as
  substrings of longer sibling module names. All new rules checked on 60 core payment, sale, PoS
  and account modules with zero hits.

## 2026-10-08: a large backend "hub" module (1,700 features) that the portal and website modules build on

- **A clean install is not the end.** The first clean install still hid twelve breaks that only
  the browser smoke test (every menu, list and form) and a flow test of the rewritten logic found:
  a missing compute on a copied core field, an unregistered `js_class`, a stat counter that failed
  on new records, a `group_expand` signature, report columns declared but never selected, a mail
  template using a removed API, a `mail.mail.send` override without the new argument (every
  outgoing mail would fail). Run the smoke test with demo data and write a flow test for every
  method you rewrote.
- **`ir.config_parameter.get_param` is gone** and no converter handles it; it also hides in QWeb
  mail templates and reports, and in modules migrated earlier whose tests never reached the call.
  Grep the whole project (scan `config-param`).
- **Renaming dead hooks can kill live code**: `_name_search` → `name_search` in a class that already
  had `name_search` silently dropped one of them (scan `duplicate-method`).
- **Name-based checks miss removed hooks of one model**: a removed `res.partner` method was not
  reported because another model still has a method of that name. `scripts/registry_check.py`
  checks the real MRO after the install.
- **A view written under another module's XML ID breaks `-u` of that module**, even when the full
  install works (it is validated before the writing module's fields exist). Own the view and switch
  the original off (scan `foreign-view-arch`).
- **Cross-module references hide in code, not only in XML IDs**: a field of a dependent module read
  in `create()`, written in `copy()`/`write()`, shown in a report, or an `env.ref()` inside a mail
  template. List the fields each dependent module defines and grep the base module for them.
- **Whole-form view coverage**: export the field and button names of the combined 17 and 20 views
  (`get_view` in a shell on both versions) and explain every name that disappeared. Here each one
  was a core rename, a field of a later module or a name used in another view; the check is cheap
  and finds lost view extensions that an install never reports.
- **Smoke test and group-restricted menus**: a menu limited to one of the module's own groups is
  not shown to admin, so the click test failed on it. `smoke_test.py` now gives admin the
  module's groups first.
- **`xpath_check.py`** lists every view locator Odoo 20 cannot apply in one run, without installing
  the module (each spec node applied separately), instead of one install error per round.
- **Scanner fixes**: `pytz` is a WARN (still installable, no longer an Odoo requirement);
  `renamed-partner` no longer matches `.mobile-hidden` CSS or `com.odoo.mobile` (it had 112 hits in
  20 core, now 0); `company_type` in a view is its own BLOCKER rule; commented-out Python lines are
  skipped; `override-signature` only compares core methods of the same model (no more
  `sign.request._schedule_activity` against a sale order helper) and skips methods whose core
  definition spans several lines. New rules checked on all 20 core modules: zero hits, except
  `config-param`, which finds two real leftover calls in core (`mail_plugin`, `account_edi_ubl_cii`).

## 2026-10-08: same hub module, after review (widget modules, agent access, contact creation)

- **Names used through odoo modules are not imports.** `models.NewId` and `fields.datetime.now()`
  (removed from `odoo.models` / `odoo.fields` in 20) passed the real-import check, because the
  import line was `from odoo import fields, models`. They broke the creation of every typed contact
  and a stage timestamp. New scan check `odoo-attr-missing` resolves each `X.attr` on Odoo 20
  (scope-aware: a function argument named `fields` is not the module; attributes core addons add at
  load time, such as `fields.Serialized`, are known). On all of 20 core it reports two real
  leftovers in core itself (`models.ValidationError` in mail, `fields.date` in an unreachable
  branch of a commission report), nothing else. A probe script that imports Odoo must put the
  server folder on `sys.path` and fail loudly: a silent import failure made a first version of
  this check report zero hits everywhere.
- **Widgets the module uses may live in modules outside the migration scope.** Grep the smoke-test
  browser log for `Missing widget:`; here two small widget modules were added to the scope.
- **Restoring an old own-documents restriction** needs per-operation group-less rows lifted for the
  grants 20 core adds (security-ir-access.md).
- **Flow tests**: create each record variant the code branches on; no committing methods in
  rollback-only tests (tests-and-tours.md).
