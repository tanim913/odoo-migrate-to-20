# Website / public frontend JavaScript to Odoo 20 (Interactions)

## What changed

- **publicWidget is removed in 20.** `web/static/src/legacy/` does not exist; there are 0
  `publicWidget` hits in 20. There is **no compatibility layer**.
- Interactions arrived in 19. `@web/public/interaction`,
  `registry.category("public.interactions")`.
- **jQuery is removed in 20** (no `lib/jquery`, no `web._assets_jquery`). Every `$(`, `this.$el`,
  `this.$target` or `$.ajax` throws at runtime.
- **`odoo.define` is gone.** Every file under `static/src/` is an ES module.

So every publicWidget becomes an Interaction, and every jQuery call becomes DOM API. Rewrite from
behaviour. The API is `$ODOO20_SERVER/addons/web/static/src/public/interaction.js`: read its
docstrings. Real examples:
- `website_sale/static/src/interactions/add_to_wishlist.js`: rpc, dynamicContent, dynamicSelectors
- `website/static/src/interactions/*.js`: short ones like `multirange_input.js`, `modal_shown.js`
- `website/static/src/interactions/animation.edit.js`: edit-mode registration

## Skeleton

```js
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export class PropertyGallery extends Interaction {
    static selector = ".o_property_gallery";          // required
    dynamicSelectors = {
        ...this.dynamicSelectors,
        _modal: () => document.querySelector("#property_modal"),
    };
    dynamicContent = {
        ".o_next": { "t-on-click": this.onNext },
        ".o_slide": { "t-att-class": (el) => ({ active: el.dataset.idx == this.index }) },
        _modal: { "t-on-hidden.bs.modal": this.onModalHidden },
        _root: { "t-att-data-count": () => this.slides.length },
    };
    setup() {                     // sync: read DOM, init state
        this.index = 0;
        this.slides = [...this.el.querySelectorAll(".o_slide")];
    }
    async willStart() {           // async data, always wrapped in waitFor
        this.data = await this.waitFor(rpc("/property/data", { id: +this.el.dataset.id }));
    }
    start() {                     // sync, after willStart; DOM ready
        this.renderAt("my_module.gallery_extra", { data: this.data }, this.el, "beforeend");
    }
    onNext(ev) {                  // after a handler, dynamicContent re-evaluates automatically
        this.index = (this.index + 1) % this.slides.length;
    }
    destroy() {}                  // listeners/renderAt output are cleaned automatically
}
registry.category("public.interactions").add("my_module.property_gallery", PropertyGallery);
```

## Translation table

| publicWidget (≤19) | Interaction (20) |
|---|---|
| `publicWidget.registry.X = publicWidget.Widget.extend({selector: ".x"})` | `class X extends Interaction { static selector = ".x" }` + `registry.category("public.interactions").add("mod.x", X)` |
| `events: {"click .btn": "_onClick"}` | `dynamicContent = {".btn": {"t-on-click": this.onClick}}` (handlers get the event; `ev.currentTarget` is the matched el) |
| event on the root el itself | `_root: {"t-on-click": ...}`; also `_body`, `_window`, `_document` |
| `"submit form"` + `ev.preventDefault()` | `"form": {"t-on-submit.prevent": this.onSubmit}` (modifiers `.prevent .stop .capture .once .noUpdate`) |
| `read_events` / `edit_events`, `disabledInEditableMode: false`, `this.editableMode` | a separate `*.edit.js` registering `registry.category("public.interactions.edit").add("mod.x", {Interaction: X, mixin: (I) => class extends I {...}})`; edit files go in `website.assets_inside_builder_iframe`, not `web.assets_frontend` |
| `start() { return this._super(...).then(...) }` / `willStart` | `async willStart()` for data (`await this.waitFor(promise)`), sync `start()` |
| `this.$el` / `this.$(".a")` / `this.$target` | `this.el` / `this.el.querySelector(".a")` / `this.el.querySelectorAll` |
| `$el.addClass/removeClass/toggleClass` | `"t-att-class": () => ({cls: cond})` in dynamicContent, or `el.classList.*` then nothing (manual changes are not tracked) |
| `$el.text(v)` / `.html(v)` | `"t-out": () => v` in dynamicContent / `this.renderAt(...)` |
| `$el.attr/prop/val` | `"t-att-name": () => v` / `el.value` |
| `$el.show()/hide()` | `"t-att-class": () => ({"d-none": !cond})` |
| `$.ajax`, `ajax.jsonRpc(url, "call", params)`, `this._rpc({route, params})` | `await this.waitFor(rpc(url, params))` (`@web/core/network/rpc`); route must be `type="jsonrpc"` |
| `this._rpc({model, method, args})` | `this.services.orm.call(model, method, args)` (public user: only if the method is exposed; prefer a controller route) |
| `this.call("dialog", "add", C, props)`, `bindService` | `this.services.dialog.add(C, props)`, `this.services.notification.add(msg)` |
| `this.trigger_up("x", data)` | `this.el.dispatchEvent(new CustomEvent("x", {bubbles: true, detail: data}))`, or a service |
| `core.qweb.render("t", ctx)` + append | `this.renderAt("t", ctx, targetEl, "beforeend")` (auto-removed on destroy) |
| mount an Owl component in the page | `this.mountComponent(targetEl, Component, props)` |
| `setTimeout/setInterval` | `this.waitForTimeout(fn, ms)` / `this.registerCleanup(() => clearInterval(id))` |
| `$(window).on("scroll", h)` | `_window: {"t-on-scroll": this.onScroll}` or `this.addListener(window, "scroll", h)` |
| `_.debounce(fn)` | `this.debounced(fn, ms)` |
| `destroy() { this._super(); ... }` | `destroy()`; plus `registerCleanup(fn)` for anything manual |
| `publicWidget.registry.WebsiteSale.include({...})` (patch core widget) | find the 20 interaction (`ProductPage`, `ShopPage`, `CartLine`, `Checkout`, `AddToCart` in `website_sale/static/src/interactions/`) and `patch(ProductPage.prototype, {...})`; add dynamic content with `patchDynamicContent(this.dynamicContent, {...})` from `@web/public/utils` inside a patched `setup()` |
| `<owl-component name="x">` + `registry.category("public_components")` | still supported (`web/static/src/public/public_component_interaction.js`) |
| Bootstrap jQuery plugins `$(el).modal("show")`, `.collapse()`, `.tooltip()` | `Modal.getOrCreateInstance(el).show()` (global `Modal`, `Collapse`, `Tooltip` from Bootstrap 5) or data attributes `data-bs-toggle` |
| slick/owl-carousel jQuery plugins | Bootstrap 5 carousel (`data-bs-ride`), CSS scroll-snap, or a vendored non-jQuery lib under `static/lib/` |

Rules:
- A handler that changes state must not also update the DOM by hand when dynamicContent can do it.
  `updateContent()` runs after each handler (unless `.noUpdate`).
- Anything async must go through `this.waitFor(...)`. It drops the result if the interaction was
  destroyed meanwhile.
- The selector must match the markup the server renders in 20. If the template changed (e.g.
  website_sale), fix the selector against the 20 template.
- Interactions are **stopped in the website editor** unless registered in
  `public.interactions.edit`.

## Frontend RPC and controllers

| Version | Frontend RPC |
|---|---|
| ≤16 | `web.ajax` |
| 17 | `jsonrpc` from `@web/core/network/rpc_service` |
| 18+ | `rpc(url, params, settings)` from `@web/core/network/rpc` |

- `odoo.csrf_token` still exists for plain form POSTs.
- Controller `type='json'` becomes `type='jsonrpc'`. 20 still accepts `'json'` as a deprecated
  alias with a warning.

## Frontend bundles in 20

- `web.assets_frontend`, `web.assets_frontend_minimal`, `web.assets_frontend_lazy`
- `web._assets_primary_variables`, `web._assets_secondary_variables`,
  `web._assets_frontend_helpers`
- `website.assets_wysiwyg`, `website.assets_editor`, `website.website_builder_assets`,
  `website.assets_inside_builder_iframe`
- `html_builder.assets`, `html_builder.iframe_add_dialog`

Gone: `web.assets_common`, `web_editor.*`, `website.assets_wysiwyg_inside`,
`website.assets_all_wysiwyg`, `web._assets_jquery`.

## Detection

`scan.py` area `website-js`:
- `publicWidget|public_widget|web\.public\.widget|odoo\.define\(`
- `\$\(|jQuery|\.\$el\b|\$target|\$\.ajax`
- `web\.ajax|ajax\.jsonRpc|this\._rpc\(|rpc_service|trigger_up\(`
