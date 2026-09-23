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
