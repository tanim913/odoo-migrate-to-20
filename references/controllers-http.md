# Controllers and HTTP to Odoo 20

## `odoo.http` is a package in 20

`odoo/http/__init__.py` re-exports only `request`, `Response`, `Controller`, `route` and
`request_var`. Importing anything else from `odoo.http` is an **ImportError at module load**, which
blocks install.

| Old import | Odoo 20 |
|---|---|
| `from odoo.http import content_disposition` | `from odoo.http.stream import content_disposition` |
| `from odoo.http import Stream, STATIC_CACHE` | `from odoo.http.stream import Stream, STATIC_CACHE` |
| `from odoo.http import serialize_exception` | `from odoo.http.dispatcher import serialize_exception` |
| `from odoo.http import SessionExpiredException, Session` | `from odoo.http.session import ...` |
| `from odoo.http import db_list, db_filter, dispatch_rpc, root` | `from odoo.http.router import ...` |

Before writing a new import, confirm it:
`grep -rn "^def <name>\|^class <name>\|^<name> =" $ODOO20_SERVER/odoo/http/`.

## Route and request changes

| Since | Old | Odoo 20 | Kind |
|---|---|---|---|
| 19 | `@http.route(..., type='json')` | `type='jsonrpc'` ('json' still accepted with a warning). `upgrade_code` only fixes it inside `controllers/` with a trailing comma, so grep for leftovers | W, UC partial |
| 16 | `request.jsonrequest` | `request.get_json_data()` | R |
| 19 | `request.cr`, `request.uid`, `request.context` | `request.env.cr`, `request.env.uid`, `request.env.context` | W |
| **20** | `request.website` | `request.env.website` (in models: `self.env.website`) | R |
| 20 | `website.get_current_website()` | `self.env.website` | R |
| 19 | `request.website.sale_get_order()` | `request.cart` | R |
| 16 | `from odoo.addons.web.controllers.main import X` | the split modules: `odoo.addons.web.controllers.home`, `.session`, `.dataset`, `.binary`, `.export`, `.action`, `.report`, `.utils`. Grep `class X` in `addons/web/controllers/` | B |
| 19 | `auth='user'/'public'/'none'` | unchanged; new `auth='bearer'` (needs `bearer_scope`) and `type='json2'` | – |
| 19 | overriding a route | an override cannot change `type`; loosening `readonly` is reverted | – |

Portal and website controller hook changes are in website-sale-portal.md.

## Checks for every controller

- An override of a core controller method must match the **20** signature. Open the core method and
  compare the arguments and the return type.
- Routes called from JS with `rpc()` must be `type='jsonrpc'`. Plain `<form method="post">` targets
  stay `type='http'` and need `csrf_token`.
- Where a method returns `request.render(...)`, check that the template id still exists in 20.
