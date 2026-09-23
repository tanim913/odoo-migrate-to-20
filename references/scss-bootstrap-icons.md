# SCSS, Bootstrap and icons to Odoo 20

## Bootstrap

- 14/15: 4.3.1. 16/17: 5.1.3. 18–20: 5.3.3.
- There is no compat layer, so BS4 classes and attributes silently stop working: dropdowns and
  modals don't open, spacing is wrong.

| Bootstrap 4 | Bootstrap 5 |
|---|---|
| `data-toggle`, `data-target`, `data-dismiss`, `data-ride`, `data-slide` | `data-bs-toggle`, `data-bs-target`, `data-bs-dismiss`, `data-bs-ride`, `data-bs-slide` |
| `ml-*` `mr-*` `pl-*` `pr-*` | `ms-*` `me-*` `ps-*` `pe-*` |
| `float-left/right`, `text-left/right` | `float-start/end`, `text-start/end` |
| `form-group` | `mb-3` |
| `custom-select` | `form-select` |
| `custom-control custom-checkbox` | `form-check` (+ `form-check-input`) |
| `form-row` | `row g-2` |
| `badge-primary` … | `text-bg-primary` … |
| `badge-pill` | `rounded-pill` |
| `sr-only` | `visually-hidden` |
| `btn-block` | wrap in `d-grid` |
| `card-deck` | `row row-cols-*` |
| `jumbotron` | `p-5 bg-body-tertiary rounded` |
| `no-gutters` | `g-0` |
| `font-weight-bold`, `font-italic` | `fw-bold`, `fst-italic` |
| `close` button | `btn-close` |
| `input-group-append/prepend` | remove the wrapper |
| `$(el).modal('show')` | `Modal.getOrCreateInstance(el).show()` |

## Icons: Font Awesome is removed in 20

- Odoo 20 no longer loads `font-awesome.css`. `fa fa-*` renders as an empty box in the backend,
  website, reports and emails.
- The 20 icon font is Material Symbols ligatures via the `oi` class.
- The font is a **subset**: only names listed in
  `$ODOO20_SERVER/addons/web/tooling/icons/icons_wishlist.txt` render.

| Old | Odoo 20 |
|---|---|
| `<i class="fa fa-trash"/>` | `<i class="oi" data-icon="delete"/>` |
| `<i class="fa fa-check text-success"/>` | `<i class="oi text-success" data-icon="check"/>` |
| button `icon="fa-pencil"` (view arch) | `icon="edit"`; a leftover `fa-` value renders a broken icon |
| `fa-spin` | `oi oi-spin`: check with `grep -n "spin" $ODOO20_SERVER/addons/web/static/src/webclient/icons.scss` |
| filled variant | class `oi-filled` |

Mapping procedure:
1. Collect the unique `fa-*` names used by the module (`scan.py` lists them).
2. For each, find the Material Symbols equivalent that is **present in `icons_wishlist.txt`**.
   Prefer the name core already uses for the same meaning:
   `grep -rhoE 'data-icon="[a-z_]+"' $ODOO20_SERVER/addons | sort | uniq -c | sort -rn`.
3. If no listed name fits, choose the closest listed one and note it in the report. Do not load
   Font Awesome from a CDN.

Common mapping, each checked against icons_wishlist.txt at the time of writing (re-grep before use):

| fa | oi | fa | oi | fa | oi |
|---|---|---|---|---|---|
| trash | delete | pencil / edit | edit | plus | add |
| check | check | times / close | close | search | search |
| home | home | user | person | users | group |
| envelope | mail | phone | phone | map-marker | location_on |
| heart | favorite | star | star | shopping-cart | shopping_cart |
| download | download | upload | upload | print | print |
| cog / gear | settings | info-circle | info | exclamation-triangle | warning |
| arrow-left/right | arrow_back / arrow_forward | chevron-left/right | chevron_left / chevron_right | bars | menu |
| calendar | calendar_today | clock-o | schedule | eye | visibility |
| file | description | image | image | external-link | open_in_new |

## SCSS

- Assets must compile. An SCSS error breaks the **whole bundle**.
- `$o-social-colors` is removed in 20.
- `web._assets_primary_variables` is the place for variable overrides.
- Use Bootstrap 5 variables and CSS custom properties (`var(--bs-primary)`). BS4 mixins such as
  `media-breakpoint-*` still exist.
- Dark mode: `web.assets_web_dark` bundle.
