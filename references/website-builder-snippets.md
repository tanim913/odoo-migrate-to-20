# Website builder, snippets and themes to Odoo 20

## Timeline

| Version | Editor | Snippet options |
|---|---|---|
| ≤18 | `web_editor` | `options.registry.X = options.Class.extend({...})` (`@web_editor/js/editor/snippets.options`) + XML `website.snippet_options` inherit with `<div data-js="X" data-selector=".s_x">` + `<we-select>`/`<we-button data-select-class>` |
| 19 | `web_editor` removed; `html_builder` + `website/static/src/builder` | `Plugin` with `resources = { builder_options: [Cls] }`, `static selector` |
| **20** | same | `builder_options` resource **gone**; options register in `registry.category("website-options")` and are declared in XML by extending `website.BuilderOptions`; `*_selector` resource keys renamed with an `s` (`dropzone_selectors`, `is_movable_selectors`, `so_content_addition_selectors`, …) |

So 18 and older snippet options need a rewrite, and 19 options need rework too.

## Odoo 20 option pattern

Copy it from `website_sale/static/src/website_builder/add_to_cart_option*.js` and
`website_sale_options.xml`. Check with
`grep -rn "BaseOptionComponent\|website-options" $ODOO20_SERVER/addons/website_sale/static/src/website_builder/`.

```js
// static/src/website_builder/my_option.js   → bundle website.website_builder_assets
import { BaseOptionComponent } from "@html_builder/core/base_option_component";
import { BuilderAction } from "@html_builder/core/builder_action";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

export class MyOption extends BaseOptionComponent {
    static id = "my_option";
    static template = "my_module.MyOption";
}
registry.category("website-options").add(MyOption.id, MyOption);

export class MyAction extends BuilderAction {
    static id = "myAction";
    apply({ editingElement, value }) { editingElement.dataset.x = value; }
}
class MyPlugin extends Plugin {
    static id = "myPlugin";
    resources = {
        builder_actions: { MyAction },
        so_content_addition_selectors: [".s_my"],
    };
}
registry.category("website-plugins").add(MyPlugin.id, MyPlugin);
```

```xml
<!-- static/src/website_builder/my_option.xml -->
<t t-inherit="website.BuilderOptions" t-inherit-mode="extension">
    <xpath expr="//t[@id='snippet_specific_options']" position="after">
        <my_option selector=".s_my"/>
    </xpath>
</t>
<t t-name="my_module.MyOption">
    <BuilderRow label.translate="Style">
        <BuilderSelect>
            <BuilderSelectItem classAction="'s_my_a'">A</BuilderSelectItem>
            <BuilderSelectItem classAction="'s_my_b'">B</BuilderSelectItem>
        </BuilderSelect>
    </BuilderRow>
</t>
```

| Old `we-*` option | 20 |
|---|---|
| `<we-select><we-button data-select-class="a">` | `<BuilderSelect><BuilderSelectItem classAction="'a'">` |
| `data-select-style` | `styleAction` |
| `data-select-data-attribute` | `dataAttributeAction` |
| `<we-checkbox data-select-class="x">` | `<BuilderCheckbox classAction="'x'"/>` |
| custom JS method `selectFoo` | a `BuilderAction` with `apply`/`isApplied`/`getValue` |
| `onBuilt`, `cleanForSave` hooks | plugin resources (`on_snippet_dropped_handlers`, `clean_for_save_handlers`, …); grep the exact name in `html_builder/static/src/` |

- A template-only option needs no JS class.
- `BaseOptionComponent` lives at `@html_builder/core/base_option_component` in 20 (in 19 it was
  `@html_builder/core/utils`).

## Registering a custom snippet in the panel

| Version | Registration |
|---|---|
| 16/17 | `<xpath expr="//div[@id='snippet_structure']/div[hasclass('o_panel_body')]" position="inside"><t t-snippet="mod.s_x" t-thumbnail="/mod/static/src/img/s_x.svg"/></xpath>` in a `website.snippets` inherit |
| 18+ | `website.snippets` has `<snippets id="snippet_groups">`, `snippet_structure`, `snippet_content`, `snippet_custom` |

- New snippet: add `<t t-snippet="mod.s_x" string="X" group="content"><keywords>…</keywords></t>`
  inside `//snippets[@id='snippet_structure']`.
- Groups: `intro`, `columns`, `content`, `images`, `people`, `text`, `contact_and_forms`, …
- A new group goes after `//t[@id='installed_snippets_hook']` (see
  `website_blog/views/snippets/snippets.xml`).
- Read `$ODOO20_SERVER/addons/website/views/snippets/snippets.xml` for the current structure.
- The snippet root is `<section class="s_x" data-snippet="s_x" data-name="X">`. Thumbnails are
  needed only on groups.

Snippet runtime JS (sliders, counters) is an Interaction. See website-interactions.md, and register
the edit-mode variant if it must run in the editor.

## Themes

- `theme.utils` hooks are stable 15 to 20: `_<theme>_post_copy(self, mod)`, `enable_view`,
  `disable_view`, `enable_asset`, `disable_asset`, `_reset_default_config`. 20 adds
  `set_page_option`.
- `website.template_header_*` ids changed in 17:
  - Removed: `template_header_centered_logo`, `_contact`, `_hamburger_full`, `_image`,
    `_magazine`, `_slogan*`, `option_header_off_canvas*`.
  - Added: `template_header_sales_one…four`, `_search`, `_stretch`, `_mobile*`.
  - `enable_view()` on a removed id fails. Check each id in
    `$ODOO20_SERVER/addons/website/views/website_templates.xml`.
- 20: `header_search_box_input` became `website_search_box_input`.
- SCSS maps `$o-website-values-palettes`, `$o-theme-font-configs` and `$o-color-palettes` are
  stable. `$o-social-colors` is removed in 20.
- Theme tours use `registerThemeHomepageTour` from `@website/js/tours/tour_utils`; the
  `changeOption` signature changed in 19.
- A theme copied from a third-party vendor (Emipro, Droggol, Atharva…) usually has an upstream 20
  release. Prefer that, and ask the user.
