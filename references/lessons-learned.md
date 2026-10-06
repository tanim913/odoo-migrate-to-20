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
- **Licences travel with code.** The fork claimed LGPL-3 on OEEL-1 enterprise code; the rebased
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
