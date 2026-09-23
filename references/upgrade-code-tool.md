# The Odoo 20 `upgrade_code` tool

Odoo ships a source rewriter: `$ODOO20_SERVER/odoo/cli/upgrade_code.py`, with one script per
change in `$ODOO20_SERVER/odoo/upgrade_code/`. Always run it through
`scripts/run_upgrade_code.sh`, never by hand, because of the traps below.

## Traps (verified against Odoo 20.0)

- **Never run it through `odoo-bin`.** That mode appends the core addons directories to the addons
  path, so the scripts rewrite core files too.
- **Never run `--from <version>` with core on the addons path.** It loads the l10n/account scripts,
  which walk the core `l10n_*` modules and crash (`KeyError: 'ar_base'` in
  `19.3-00-account-groups.py`).
- **Standalone mode needs `odoo` importable** (`PYTHONPATH=$ODOO20_SERVER`) and Python 3.12+
  (`$ODOO20_PYTHON`), because the scripts import `odoo.upgrade_code.tools_*`.
- **`owl3-migration.py` is never selected by `--from`**: its name has no version. Run it with
  `--script owl3-migration`.
- The command exits **1 when it changed files**, 0 when nothing changed. Neither means failure.
- `--glob` is relative to each addons path entry. `--glob '<module>/**/*'` restricts writes to one
  module while other entries of the addons path stay readable. `19.4-00-ir-access` relies on this:
  it reads core `res.groups` definitions to infer implied groups.

The wrapper therefore runs, one `--script` at a time:

| Script | Runs when source < | Addons path | Rewrites |
|---|---|---|---|
| `17.5-01-tree-to-list` | 17.5 | module only | `<tree>` tags, `tree` in `view_mode`, `binding_view_types`, xpath `/tree`, `tree_view_ref`, `env.ref('..tree')`. Regex: check for false hits on words containing "tree". |
| `18.1-00-sql-constraint` | 18.1 | module only | `_sql_constraints = [...]` to `_name = models.Constraint("...", "msg")`. Fails on lists containing `]`; never emits `Index`/`UniqueIndex`; assumes `models` is imported. Logs "Failed to replace". |
| `18.1-02-route-jsonrpc` | 18.1 | module only | `type='json',` to `type='jsonrpc',`, **only in `controllers/`** and only when a comma follows. Grep for leftovers. |
| `18.5-00-deprecated-properties` | 18.5 | module only | `._cr` / `._uid` / `._context` to `.env.cr` / `.env.uid` / `.env.context` in `.py`. |
| `18.5-00-domain-dynamic-dates` | 18.5 | module only | `context_today()` / `relativedelta` in XML domains (`data/`, `report/`, `views/`) to `'today -1m'` syntax. Optional, since the old syntax still evaluates. |
| `19.1-00-t-call` | 19.1 | module only | `<t t-call="x"><t t-set="a" t-value="b"/></t>` to `<t t-call="x" a="b"/>` (also `a.f=`, `a.translate=`). Only XML outside `static/`. Skips t-calls inside `<kanban>` or with non-`t-` attributes and logs them, so fix those by hand. |
| `19.3-00-base64-in-xml` | 19.3 | module only | `type="base64" file=` to `type="bytes"`. |
| `19.4-00-ir-access` | 19.4 | **module + core + enterprise, `--glob '<module>/**/*'`** | Merges `ir.model.access.csv` and XML `ir.model.access`/`ir.rule` records into `security/ir.access.csv`, deletes the old files/records, fixes the manifest `data` list. Rows without a group become `base.group_everyone`. Prints WARNING/ERROR lines for what it cannot convert, so review every one. |
| `19.4-00-ormcache-on-transaction` | 19.4 | module only | `registry.clear_cache` to `transaction.invalidate_ormcache`. Not `clear_caches()`. |
| `19.5-00-tuple-rec_names_search` | 19.5 | module only | `_rec_names_search` list to tuple (style). |
| `owl3-migration` | always if `static/` | module only | See below. |

Skipped for custom modules unless the module is `l10n_*`: `18.2-00-l10n-translate`,
`18.3-00-l10n-fiscal-position-taxes`, `18.5-00-no-tax-tag-invert`, `19.3-00-account-groups`,
`19.3-00-account-report-foldable`.

## What `owl3-migration` does, and where it is wrong

It runs on `static/**/*.js` and `static/**/*.xml` only, in this order: useEffect, onWillRender,
onRendered, useComponent, useEnv, useSubEnv, useChildSubEnv, useRef, useState to proxy, reactive
to proxy (1-argument form only), useExternalListener, t-portal, t-esc, t-ref, t-model, `this.` in
templates, `this.` in test fragments, t-slot, parametric t-call, useService to usePlugin (22 mapped
services).

Fix these after it runs. `scan.py` flags all of them.

1. It moves `useRef`, `useExternalListener`, `useComponent`, `onRendered` and `useChildSubEnv`
   imports to `@web/owl2/utils`, which exports only `render`, `onWillRender`, `useLayoutEffect`,
   `useEnv` and `useSubEnv`. The result fails at runtime. Rewrite them:
   `useRef("x")` + `t-ref="x"` becomes `x = signal.ref()` + `t-ref="this.x"`, read with `this.x()`.
   `useExternalListener(t, ev, h)` becomes `useListener(t, ev, (e) => this.h(e))`.
   `useComponent()` becomes `useScope().component`.
2. It writes `t-custom-ref` / `t-custom-model`, which are **not defined** in Odoo 20 (Owl throws
   `Custom directive "…" is not defined`). Convert to `signal.ref()` / `signal()` by hand.
3. `useEffect(fn, () => deps)` becomes `useLayoutEffect` from `@web/owl2/utils`. That works, but
   check that the deps semantics still make sense.
4. It never converts `static props` / `static defaultProps`, which **throw** in Odoo 20. Convert to
   `props = useProps({...})` (see backend-js-owl3.md).
5. It prefixes every free template variable with `this.`. Templates rendered with
   `renderToString` / `renderToElement` / `renderAt` / QWeb in interactions get their values from
   a context, not a component. Revert `this.` in those.
6. The `sortable` service mapping points to the wrong path (`@web/core/util/sortable_plugin`
   instead of `@web/core/utils/sortable_plugin`).

## Not handled by any script (manual, see the other references)

attrs/states, server QWeb `t-esc`/`t-raw` in `views/`/`report/`/`data/`, name_get, `_name_search`,
read_group, groups_id to group_ids, res.groups category_id to privilege_id, oe_chatter,
kanban-box, odoo.osv, odoo.http submodule imports, field renames, manifest version, `@api.model`
create, publicWidget/jQuery, Font Awesome, Bootstrap 4, snippet options, portal entries,
website_sale ids and routes, `request.website`.
