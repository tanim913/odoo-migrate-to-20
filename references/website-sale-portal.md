# eCommerce (website_sale), website pages and portal to Odoo 20

## Rule 1: re-diff every override against the 20 template

Custom modules most often inherit `website_sale.product`, `cart_lines`,
`products`, `cart` and `products_item`. In 20:
- the templates moved to `website_sale/templates/{product_page,shop_page,checkout/*}_templates.xml`;
- markup changed;
- the JS became interactions bound to new classes.

For each inherited template:
1. `grep -rn 'id="<tmpl>"' $ODOO20_SERVER/addons/website_sale/` to find it, or confirm it is
   gone.
2. Read the 20 template and rewrite each xpath against its real structure, anchoring on
   `@id`, `@name`, `hasclass('…')`.
3. If a custom template **replaces** a core one, start again from the 20 core template and re-apply
   the customisation. Keep every core class and id: `oe_website_sale`, `o_wsale_*`,
   `js_product`, `o_wsale_product_page`, `o_cart_product`, `#o_wsale_container` classes. The 20
   interactions select on them. Missing classes caused 32 responsive/JS regressions in the user's
   16→19 migration.

## Template ids removed

| Step | Removed (frontend-relevant) |
|---|---|
| 16→17 | `cart_popover`, `cart_summary`, `short_cart_summary`, `extra_info_option`, `payment_footer`, `payment_sale_note` |
| 17→18 | `cart_delivery`, `payment_delivery`, `payment_delivery_methods`, `products_fiscal_position`, `row_addresses` |
| 18→19 | `address_kanban`, `address_on_payment`, `address_row`, `billing_address_row`, `delivery_address_row`, `add_to_cart_redirect`, `products_add_to_cart`, `product_variants`, `product_custom_text`, `product_share_buttons`, `products_description`, `products_design_*`, `products_thumb_*`, `product_picture_magnify_*`, `o_wsale_offcanvas_color_attribute`, `s_add_to_cart_options`, `add_grid_or_list_option` |
| 19→20 | `pricelist_list`, `products_list_view`, `product_category_extra_link`, `s_mega_menu_*` |

## Markup and JS

| Old | Odoo 20 |
|---|---|
| cart `<table id="cart_products">` rows (16) | `<div id="cart_products">` with `.o_cart_product` (17+) |
| `#add_to_cart`, `.a-submit`, `js_add_cart_json` | `<button name="add_to_cart" data-action="add_to_cart">` / `data-action="buy_now"` |
| product tile title `h6.o_wsale_products_item_title` | `h2` (19+) |
| `WebsiteSale` publicWidget (`website_sale.website_sale`), `VariantMixin`, `sale.VariantMixin` | interactions `ProductPage` (`.o_wsale_product_page`), `ShopPage`, `CartLine` (`.o_cart_product`), `Checkout` (`#shop_checkout`), `AddToCart`, and the `cart` service (`website_sale/static/src/js/cart_service.js`); `VariantMixin` is gone |
| `website_sale_options.website_sale` / product configurator widgets | the 20 product configurator dialog (`sale/static/src/js/product_configurator_dialog/`) |

## Routes and Python

| Old | Odoo 20 |
|---|---|
| `/shop/cart/update_json` | `/shop/cart/add` (`product_template_id`, `product_id`, `quantity`, …) jsonrpc |
| `/shop/cart/update` form POST (≤18) | jsonrpc `update_cart(line_id, quantity)` (19+) |
| `/shop/cart/clear`, `/shop/cart/quantity` | removed |
| `request.website.sale_get_order(force_create=True)` | `request.cart` (create with the cart helpers; grep `def _get_cart\|request.cart` in `website_sale/`) |
| `order._cart_update(product_id, line_id, add_qty, set_qty)` | `order._cart_add(...)` / `order._cart_update_line_quantity(line_id, quantity)` |
| controller `_get_mandatory_billing/shipping_address_fields`, `_check_delivery_address` | moved to `res.partner` (`portal/models/res_partner.py`) |
| `sale.order.shop_warning` | `_add_warning_alert` |
| `request.website` | `request.env.website` |

## Portal

| Old | Odoo 20 |
|---|---|
| `_prepare_home_portal_values(self, counters)` override adding `x_count` | `_prepare_portal_counter_values(self, counter)` returning `(model, domain, access)` (see `sale/controllers/portal.py`) |
| xpath into `portal.portal_my_home` `#portal_client_category` / `#portal_service_category` / `#portal_vendor_category` / `#portal_common_category` + `<t t-call="portal.portal_docs_entry"><t t-set="title" …/>` | the category divs are **gone** (xpath blocks install). Home cards are `portal.entry` records, below |
| `portal.portal_docs_entry` params `title`, `url`, `placeholder_count`, `icon`, `text`, `config_card`, `show_count`, `bg_color` | reads `entry.url`, `entry.name`, `entry.placeholder_count` |
| `portal.portal_layout`, `portal.portal_table`, `pager()` | unchanged |

```xml
<record id="portal_my_rfqs" model="portal.entry">
    <field name="name">My RFQs</field>
    <field name="url">/my/rfqs</field>
    <field name="placeholder_count">rfq_count</field>
    <field name="category">client_category</field>
    <field name="image" type="bytes" file="my_module/static/img/rfq.svg"/>
</record>
```

Confirm the `portal.entry` fields first: `grep -n "fields\." $ODOO20_SERVER/addons/portal/models/portal_entry.py`.
For a sample, see `$ODOO20_SERVER/addons/sale/data/portal_entry_data.xml`.

## Website pages and forms

- `website.page` records: `date_publish` is removed. `url`, `view_id`, `is_published` and
  `website_indexed` are unchanged.
- `website.menu` records: unchanged (`name`, `url`, `parent_id`, `sequence`).
- `website.layout`, `website.homepage`, `website.footer_custom`, `website.navbar`,
  `website.navbar_nav` and `website.submenu` are stable ids.
- Website forms (`s_website_form`, `/website/form/<model>`, `data-model_name`) are stable.
  - Model hook: `_get_form_writable_fields(self, property_origins=None)` (18+).
  - Editor-side form actions: `registry.category("website.form_editor_actions")` in a `*.edit.js`
    file.
