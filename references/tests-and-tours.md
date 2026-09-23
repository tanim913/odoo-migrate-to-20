# Tests and tours on Odoo 20

Read this when the module has `tests/`, `static/tests/`, or any file that registers a tour, and
before writing a flow tour for the smoke test (step 6).

Everything here was checked against the Odoo 20 source:
- the tour schema: `addons/web_tour/static/src/tour_plugin.js`;
- the step runner: `addons/web_tour/static/src/tour_step.js`;
- the run helpers: `addons/web_tour/static/src/tour_helpers/`;
- Python: `odoo/tests/common.py` (`HttpCase.start_tour`, `browser_js`).

Odoo's online "Testing Odoo" page still shows `tour.register` and PhantomJS. **Trust the 20 source
over the doc.**

## Why tours break silently

Odoo 20 validates every tour with a **strict** schema. An unknown key logs
`Error in schema for TourStep` through `console.error`, and any console error fails the HttpCase.
Three changes break old tours without any error in the tour file itself:

- **Implicit click.** Up to Odoo 17, a step without `run` clicked its trigger (`actionHelper.auto()`,
  17's `tour_compilers.js`). Since 18, a step without `run` **only waits** for its trigger. An old
  tour then stalls on the next step and times out.
  - `scan.py` flags these steps (`tour-implicit-click`) when the source version is below 18.
  - Add `run: "click"` where the old tour relied on the click. Leave it out where the step was only
    a check.
- **Start page.** Up to 19, starting a tour redirected to the `url` it was registered with. In 20,
  a test tour starts on the page that `start_tour(url_path, name)` opens, and the registered `url`
  is ignored (`tour_plugin.js` only redirects to `options.url`). An old test with
  `start_tour("/web", "x")` now runs on the home screen and times out on its first step.
  - Move the tour's `url` into the Python call: `start_tour("/odoo/action-my_module.my_action", "x")`.
  - `scan.py` flags registered `url`s in `static/tests` (`tour-url-ignored`). Onboarding tours
    still use `url`.
- **`run` context.** A `run` function is called with `this = { anchor: Element }` and one argument,
  the `TourHelpers`. `this.$anchor` (jQuery) is gone. Use `this.anchor` or `helpers.click()`,
  `helpers.edit("x")` and so on.

## Registering a tour: old → 20

| Source version | Old | Odoo 20 |
|---|---|---|
| 14–16 | `odoo.define("x", function (require) { var tour = require("web_tour.tour"); tour.register("name", {test: true, url: "/web"}, [ ...steps ]); })` | ES module + registry (below) |
| 16 (ES) | `import tour from "web_tour.tour"; tour.register(...)` | same |
| 17 | `registry.category("web_tour.tours").add("name", {test: true, url, steps: () => [...]})` | drop `test` |
| 18–19 | registry form | check step keys and `run` helpers; the registered `url` no longer applies to test runs |

```js
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("my_module_flow", {
    // no url: the Python test chooses the start page
    steps: () => [                              // a FUNCTION returning the steps
        {
            content: "Create a record",         // logged: makes failures readable
            trigger: ".o_list_button_add",
            run: "click",
        },
        ...stepUtils.saveForm(),
    ],
});
```

- **Tour options:** only `steps` (a function) and `url` are allowed, and `url` is only used by
  onboarding runs. Remove `test`, `sequence`, `wait_for`, `checkDelay`, `rainbowMan` and `saveAs`.
  `timeout` belongs on a step, not on the tour.
- **Asset bundle:** test tours go in `'web.assets_tests': ['my_module/static/tests/tours/**/*']`.
  Onboarding tours (shown to users) go in `web.assets_backend`, plus a `web_tour.tour` record in data
  XML.
- **Website:**
  - `registerWebsitePreviewTour(name, {url, edition: true}, () => [...])` comes from
    `@website/js/tours/tour_utils`, and its `steps` argument must be a function too;
  - theme tours use `registerThemeHomepageTour` (see `website-builder-snippets.md`);
  - triggers inside the edited page use the `:iframe` prefix.

## Step keys (Odoo 20 schema)

Allowed keys:
- `trigger` (required), `run`, `content`, `isActive`, `id`, `tooltipPosition`, `timeout`
  (0–60000), and `expectUnloadPage` (set it on the step whose action loads a new page);
- in `debug=True` runs only: `pause` and `break`.

| Old key | Odoo 20 |
|---|---|
| `extra_trigger: X` | a separate step `{ trigger: X }` placed before, or a trigger folded with `:has()` or a parent selector |
| `in_modal: true` | scope the trigger: `.modal .btn-primary` |
| `position` | `tooltipPosition` |
| `edition: "enterprise"` | `isActive: ["enterprise"]` (or `"community"`) |
| `mobile: true` | `isActive: ["mobile"]` (or `"desktop"`) |
| `auto: true` | `isActive: ["auto"]` |
| `shadow_dom` | `:shadow` in the trigger |
| `isCheck: true` | delete: a step without `run` is a check |
| `allowInvisible` | `:not(:visible)` or `:hidden` in the trigger |
| `allowDisabled`, `consumeEvent`, `noPrepend`, `width` | delete |
| `run: function () {}` (empty) | delete `run`: the schema rejects empty functions |

## `run` helpers

String form: `run: "edit Agrolait"`. You can chain actions with `&&`, e.g.
`run: "click && edit 3"`. `scan.py` checks every name against the 20 helpers:
- `click`, `dblclick`, `hover`, `check`, `uncheck`, `clear`;
- `edit <text>` (clears first), `fill <text>` (appends), `editor <text>` (html fields), `press <key>`;
- `select <value>`, `selectByLabel <label>`, `selectByIndex <n>`, `range <n>`;
- `drag_and_drop <target selector>`, `scroll`, `goToUrl <url>`, `inputFiles`, `dragFiles`.

| Old | Odoo 20 |
|---|---|
| `run: "text foo"` | `run: "edit foo"` |
| `run: "text_blur foo"` | `run: "edit foo && click body"` |
| `run: "drag_and_drop_native X"` | `run: "drag_and_drop X"` |
| `run(actions) { actions.text("x") }` | `run(helpers) { await helpers.edit("x") }` |
| `this.$anchor.click()` | `this.anchor.click()` or `helpers.click()` |

## Selectors

Triggers are resolved by hoot-dom (`web/static/lib/hoot-dom/helpers/dom.js`), not jQuery:
- standard CSS works;
- Odoo's own pseudo-classes: `:contains()`, `:has()`, `:not()`, `:visible`, `:hidden`, `:first`,
  `:last`, `:eq()`, `:empty`, `:selected`, `:value()`, `:text()`, `:iframe`, `:shadow`, `:only`,
  `:displayed`, `:focusable`, `:interactive`, `:scrollable`, `:count()`;
- **jQuery-only ones fail:** `:input`, `:button`, `:checkbox`, `:radio`, `:submit`, `:odd`, `:even`,
  `:gt()`, `:lt()`, `:parent`, `:header` (`tour-jquery-selector`).

A trigger waits until its element is **visible** and, for actions, **enabled**. The failure message
tells you which one it waited for.

## Python side

```python
from odoo.tests import HttpCase, tagged

@tagged("post_install", "-at_install")
class TestMyModuleTour(HttpCase):
    def test_flow(self):
        self.start_tour("/odoo/action-my_module.my_action", "my_module_flow", login="admin")
```

The first argument is the page the tour starts on. `/odoo/action-<module>.<action_xmlid>` opens an
action directly.

- `start_tour(url_path, tour_name, step_delay=None, **browser_js_kwargs)`. Its default `ready` is
  `odoo.isTourReady(name)`: delete old `ready="odoo.__DEBUG__.services['web_tour.tour']..."`
  expressions (`py-tour-old-ready`).
- Removed: `phantom_js` / `phantom_run` (use `start_tour` or `browser_js`), and `SavepointCase` /
  `SingleTransactionCase` (use `TransactionCase`).
- Import `Form` from `odoo.tests`, not `odoo.tests.common`. `scan.py` checks every `odoo.*` import
  against a real Odoo 20 import (`py-odoo-import`).
- Public (website) tours: `self.start_tour("/shop", name)` without `login`.
- Performance regressions: `with self.assertQueryCount(N):` around a flow. Only use it when the
  source had it or the user asks; it is not a migration requirement.

## JS unit tests

QUnit is gone. Odoo 20 uses Hoot:
- `static/tests/**/*.test.js` in `web.assets_unit_tests`;
- imports come from `@odoo/hoot`, `@odoo/hoot-dom` and `@web/../tests/web_test_helpers`.

Rewriting a QUnit suite is real work. List it in the report as "to rewrite in Hoot" unless the user
asks for it. To run the Hoot suite in a browser, open `/web/tests?debug=assets` on a `--keep`
database.

## Flow tour for the smoke test (step 6)

The clickbot proves that pages load. A flow tour proves that the migrated code **works**: an Owl
widget saves, an Interaction reacts to a click, a website form submits. Write one per module when
it has backend JS, frontend JS, or a website flow. It lives in the throwaway smoke module and is not
shipped, unless the user wants it in the module's `static/tests/tours`.

1. Pick the module's main flow from its own code: the main menu action and its required fields, or
   a website route and its button or form. Take every selector from the module's 20 templates, or
   from core 20 widgets:
   - new record: `.o_list_button_add` (list) or `.o-kanban-button-new` (kanban);
   - char, integer and float fields: `.o_field_widget[name=x] input` with `run: "edit ..."`;
   - selection fields are a `SelectMenu` in 20, not a `<select>`: click
     `.o_field_widget[name=x] .o_select_menu_toggler`, then `.o_select_menu_item:contains(Label)`;
   - many2one: `edit` the `input`, then click `.o-autocomplete--dropdown-item:contains(Name)`;
   - save: `...stepUtils.saveForm()` from `@web_tour/tour_utils`.
2. Keep it short, 5–10 steps, and end in a stable state: saved form, no pending request.
3. Put `expectUnloadPage: true` on steps whose action navigates (`goToUrl`, a link, a form post).
4. Run it:
   ```bash
   eval "$(python3 $S/smoke_test.py <module> --tour-js /tmp/<module>_flow_tour.js --tour '<tour_name>@/odoo/action-<module>.<action_xmlid>' --out <tmpdir>)"
   $S/install_test.sh $MIG20_TARGET_ROOT/<project> <module>,$SMOKE_MODULE --tags /$SMOKE_MODULE:TestMigrationSmoke.test_03_flow_tours --extra-addons $SMOKE_ADDONS
   ```
   A public website tour uses `--tour '<name>@/<route>:public'`. Without `@URL`, the tour starts on
   `/odoo` (or `/` for public).

## When a tour or browser test fails

1. `install_test.sh` prints the failing step (`FAILED: [3/8] Tour x → Step …`) and the paths of
   the PNG screenshots Odoo took at that moment (`--screenshots`). **Open the images**: they
   usually show the reason at once (error dialog, wrong page, element hidden behind a modal).
2. Re-run only that test with `--tags /<module>:<Class>.<test_method>`.
3. `--screencast` records a video of the run (needs ffmpeg).
4. **Humans only (they open a real Chrome window):**
   - `self.start_tour(..., watch=True)` shows the run;
   - `debug=True` opens devtools with a breakpoint, and then honours step `break: true`, or
     `pause: true` (resume with `play()` in the console);
   - in any browser: `odoo.startTour("name")` in the console, or `?debug=tests` in the URL.

   Never leave `watch`, `debug`, `pause` or `break` in committed code.
