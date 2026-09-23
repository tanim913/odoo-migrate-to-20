# Backend web client JavaScript to Odoo 20 (Owl 3)

Odoo 20 runs **Owl 3.0** (`web/static/lib/owl/owl.js`). A temporary compatibility layer
(`web/static/src/owl2/owl3_compatibility_layer.js`) loads after it, but it does **not** keep Owl 2
components running unchanged. `web/static/src/legacy/` is gone, so no Widget, no `odoo.define`,
no jQuery. Before writing any API, open a current core component that does the same thing and copy
its shape. Good models:

- field widget: `web/static/src/views/fields/char/char_field.{js,xml}`
- view widget: `hr/static/src/components/department_chart/department_chart.js`
- systray item: `mail/static/src/core/web/activity_menu.js`
- dialog: `web/static/src/core/dialog/dialog.js`

## Framework timeline

| Odoo | Owl | Module system | Legacy layer |
|---|---|---|---|
| 14 | Owl 1 bridge | `odoo.define` | full Widget/AbstractField MVC |
| 15 | 1.4 | `/** @odoo-module **/` introduced | legacy under `web/static/src/legacy/` |
| 16 | 2.8 | ES modules, `import from "@odoo/owl"` | legacy fields/views still present |
| 17 | 2.8 | same | backend legacy MVC removed |
| 18 | 2.8 | annotation optional | public widgets only |
| 19 | 2.8 | same | public_widget + jQuery only |
| **20** | **3.0** | same | **removed** |

## 1. Owl 2 to Owl 3 (every 16 to 19 component needs this)

| Owl 2 | Owl 3 / Odoo 20 | Script? |
|---|---|---|
| `static props = {...}` / `static defaultProps` | **Throws.** Class field `props = useProps({ x: t.string().optional("dflt") })` | no |
| `{type: String, optional: true}` | `t.string().optional()`; others: `t.number() t.boolean() t.object() t.array() t.function() t.any() t.selection([...]) t.instanceOf(C) t.or([..]) t.signal(t.ref())`. Spread shared schemas: `{...standardFieldProps, myOpt: t.string().optional()}` | no |
| `this.props` implicit | only exists through `props = useProps(...)` | no |
| Template scope = component: `props.x`, `onClick`, `state.y` | Render context is `{this: component}`: write `this.props.x`, `this.onClick`, `this.state.y`. `t-foreach`/`t-set` vars stay bare | yes (static xml + `` xml`` ``) |
| `useState({...})` | `proxy({...})` from `@odoo/owl` | yes |
| `reactive(obj)` | `proxy(obj)`; 2-arg callback form: rewrite with `useEffect`/`computed` | partial |
| `useRef("x")` + `t-ref="x"`, `this.x.el` | class field `x = signal.ref()` + `t-ref="this.x"`, read `this.x()` | **broken** |
| `useEffect(fn, () => [deps])` | native `useEffect(fn)` auto-tracks signals, no deps array; explicit deps: `useOnChange(() => [deps], cb)`; compat: `useLayoutEffect` from `@web/owl2/utils` (keeps Owl 2 deps semantics) | yes (to useLayoutEffect) |
| `useExternalListener(target, "ev", this.h)` | `useListener(target, "ev", (e) => this.h(e))`. Handler is **not** bound | **broken** |
| `useComponent()` | `useScope().component` | **broken** |
| `onRendered(cb)` | removed; use `onPatched`/`onMounted` | **broken** |
| `onWillRender`, `useEnv`, `useSubEnv` | import from `@web/owl2/utils` | yes |
| `useChildSubEnv` | removed; use `useSubEnv` in a wrapper | **broken** |
| `t-model="state.x"` | `x = signal("")` + `t-model="this.x"` (must be a signal) | **broken** (emits undefined `t-custom-model`) |
| `t-portal="'sel'"` | `<Portal target="'sel'">…</Portal>`, or compat `t-custom-portal` | yes (compat) |
| `t-slot="default"` | `t-call-slot="default"` | yes |
| `t-esc` | `t-out` | yes |
| `t-ref` on a child component | not supported: pass a callback prop | no |
| `<t t-call="x"><t t-set="a" t-value="b"/></t>` | `<t t-call="x" a="b"/>` | yes |
| `useService("notification")` etc. | still works; the script may switch to `usePlugin(NotificationPlugin)`, so check the import path exists | yes (22 services) |
| `this.env.debug`, `this.env.isSmall` | **throw**. Use `odoo.debug` (string), `useService("ui").isSmall` | no |
| `useInputField({getValue, refName: "input"})` | `useInputField({ref: this.input, getValue, parse})` with `input = signal.ref()` | no |
| Dialog subclass extending `Dialog.props` | `static propsSchema = {...dialogProps, mine: t.string()}` + `props = useProps(this.constructor.propsSchema)` | no |
| `markup(str)` | unchanged (`markup` from `@odoo/owl`) | – |

Owl 3 component skeleton (from `char_field.js`):

```js
import { Component, onWillStart, proxy, signal, t, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class MyField extends Component {
    static template = "my_module.MyField";
    props = useProps({ ...standardFieldProps, placeholder: t.string().optional() });
    input = signal.ref();
    setup() {
        this.orm = useService("orm");
        this.state = proxy({ count: 0 });
    }
    get value() { return this.props.record.data[this.props.name]; }
    onChange(ev) { this.props.record.update({ [this.props.name]: ev.target.value }); }
}
registry.category("fields").add("my_field", {
    component: MyField,
    supportedTypes: ["char"],
    extractProps: ({ attrs, options }) => ({ placeholder: attrs.placeholder }),
});
```
```xml
<t t-name="my_module.MyField">
    <input t-ref="this.input" t-att-value="this.value" t-on-change="this.onChange"/>
    <span t-out="this.state.count"/>
</t>
```

Also note:
- **View widgets** (`<widget name="x"/>`): `props = useProps(standardWidgetProps)`, where
  `standardWidgetProps` from `@web/views/widgets/standard_widget_props` is
  `{readonly: t.boolean().optional(), record: t.object()}`. Registration is
  `registry.category("view_widgets").add("x", {component: X, extractProps?})`.
- **Systray**: `registry.category("systray").add("my_module.item", {Component: X}, {sequence})`.
  Items take no props, so declare no props at all (`mail/static/src/core/web/activity_menu.js`).

## 2. Pre-Owl code (14/15 `odoo.define`, 16 legacy) to Odoo 20

There is no incremental path. **Rewrite as an Owl 3 component** from the behaviour, not line by
line.

| Legacy | Odoo 20 |
|---|---|
| `odoo.define('m.x', function (require) { var W = require('web.Widget'); ... })` | ES module: `import {...} from "@web/..."`; file under `static/src/` is a module automatically |
| `AbstractField.extend({...})` + `field_registry.add` | component + `registry.category("fields").add(name, {component, supportedTypes, extractProps})` |
| `FormController/ListRenderer.include({...})` | `patch(FormController.prototype, {...})` from `@web/core/utils/patch` + `super.method(...)` |
| `AbstractAction.extend` + `core.action_registry.add` | component + `registry.category("actions").add("tag", Component)` |
| `this._rpc({model, method, args})` | `this.orm = useService("orm"); await this.orm.call(model, method, args, kwargs)` |
| `this._rpc({route, params})` / `ajax.jsonRpc` | `import { rpc } from "@web/core/network/rpc"; await rpc(route, params)` |
| `session.uid`, `session.user_context`, `useService("user")` | `import { user } from "@web/core/user"`: `user.userId`, `user.context`, `user.hasGroup("x")` |
| `useService("company")` | `user.activeCompany`, `user.allowedCompanies` |
| `core._t`, `_lt` | `import { _t } from "@web/core/l10n/translation"` (`_t` is lazy; `_lt` removed in 18) |
| `this.do_action(...)` | `useService("action").doAction(...)` |
| `this.displayNotification` | `useService("notification").add(msg, {type})` |
| `Dialog.confirm` | `useService("dialog").add(ConfirmationDialog, {body, confirm})` |
| `qweb.render("tmpl", ctx)` | `renderToString`/`renderToElement` from `@web/core/utils/render`, or a sub-component |
| `$(...)`, `this.$el` | DOM API: `this.root = signal.ref()`, `this.root().querySelector(...)` |
| `patch(Obj.prototype, "name", { m() { this._super(...arguments) } })` | `patch(Obj.prototype, { m() { return super.m(...arguments); } })`; since 17 a string 2nd arg throws |
| 16 field props `this.props.value`, `this.props.update(v)`, `props.type` | `this.props.record.data[this.props.name]`, `this.props.record.update({[this.props.name]: v})` |
| `X.extractProps = ({attrs}) => ...` + `.add("n", X)` (16) | `.add("n", {component: X, extractProps: ({attrs, options, string}, dynamicInfo) => ({})})` (17+) |
| `owl="1"` on templates (16) | remove (ignored since 17) |
| 16 mail `models/*.js` (`registerModel`, messaging system) | gone since 17; rewrite with `mail` store (`useService("mail.store")`) or plain ORM calls |
| Many2OneField props (≤18) | 19+: `Many2One` component + `buildM2OFieldDescription`/`extractM2OFieldProps` |

## 3. Views and field widgets that changed name

- Kanban: `t-name="kanban-box"` became `t-name="card"` (throws in 19+).
- **20:** custom field widgets registered as `kanban.<name>` are ignored, because card fields are
  looked up with prefix `card.`. Register them as `card.<name>`.
- Removed/renamed widget names:
  - 16 to 17: `date`, `datetime`, `daterange` (re-registered), `kanban.image`, `list.state_selection`
  - 18 to 19: `kanban.many2one`, `list.many2one`, `kanban.selection`, `jsonb`
  - 19 to 20: `remaining_days` became `relative_date`; `selection_badge` became
    `badges_selection`; all `kanban.*` became `card.*`; `list.boolean_toggle`,
    `list.selection_badge`, `form.many2many_tags`, `form.phone`, `many2many_tags_avatar_popover`,
    `kanban.progressbar`, `section_and_note_text`, `iban`, `boolean_toggle_labeled` are gone.
- Still present: `boolean_toggle badge radio many2many_tags many2many_tags_avatar many2one_avatar
  progressbar phone statusbar priority image url email html`.
- Always confirm a widget exists before using it:
  `grep -rn 'category("fields").add("<name>"' $ODOO20_SERVER/addons $ODOO20_ENTERPRISE`.

## 4. Assets

- A manifest `qweb` key is **ignored** (since 15). Move its entries into `assets` →
  `web.assets_backend`.
- XML `<template inherit_id="web.assets_backend">` asset inheritance (14) → manifest `assets`.
- Valid backend bundles in 20: `web.assets_backend`, `web.assets_backend_lazy`, `web.assets_web`,
  `web.assets_web_dark`, `web._assets_primary_variables`, `web._assets_secondary_variables`,
  `web.assets_unit_tests`, `web.icons_fonts`.
- Gone: `web.assets_common` (17), `web.assets_qweb` (16), `web._assets_jquery`,
  `web.qunit_suite_tests` (20).
- Directives: `('include', b)`, `('remove', p)`, `('replace', old, new)`, `('prepend', p)`,
  `('before', target, p)`, `('after', target, p)`.
- Every path listed must exist. A missing file fails the bundle. External `https://` URLs in a
  bundle work but are fetched at runtime; prefer vendoring the library under `static/lib/`.

## 5. Tests

QUnit (≤17) became Hoot (18+). `web.qunit_suite_tests` is gone in 20. Old QUnit tests cannot be
ported mechanically, so drop them from assets and list them in the report as "to rewrite in Hoot".
Python HttpCase tours still work.

## 6. POS

POS in 20 is its own framework (`point_of_sale/static/src/app/`, services + `app/plugins/`, still
on the Owl 2 compat layer). 14 to 16 POS code (Backbone `models.js`, `Registries.Component.extend`)
must be rewritten against the 20 `PosStore` / data models. Patch `PosStore.prototype` and the
screen components with `patch()`. Read the equivalent core file in
`point_of_sale/static/src/app/` first.

## Detection

`scripts/scan.py` area `backend-js`. Key regexes:
- `static (props|defaultProps)\s*=`
- `\b(useState|useRef|useExternalListener|useComponent|onRendered|useChildSubEnv)\(`
- `t-custom-(ref|model)`
- `@web/owl2/utils.*\b(useRef|useExternalListener|useComponent|onRendered|useChildSubEnv)\b`
- `env\.(debug|isSmall)`
- `odoo\.define\(`
- `patch\([^,]+,\s*["']`
- `useService\(["'](rpc|user|company)["']\)`
- `\b_lt\(`
- `owl="1"`
- `\.add\(["']kanban\.`
- `refName:`
