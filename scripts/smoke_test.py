#!/usr/bin/env python3
"""Generate a throwaway Odoo 20 test module that smoke-tests a migrated module in headless Chrome.

    smoke_test.py <module> [--routes /a,/b] [--tour-js FILE ...] [--tour NAME[@URL][:LOGIN] ...] [--out DIR]

Then run it with install_test.sh:

    install_test.sh <project_dir> <module>,mig20_smoke_<module> --tests --extra-addons <DIR>

What the generated HttpCase does (any browser console error fails the test):
  1. For every root menu (app) the module defines: Odoo's own clickbot
     (@web/webclient/clickbot) clicks all its menus, views and filters.
  2. For every other menu of the module (added under foreign apps): opens its action, and the
     action's "new record" form when it has one.
  3. Website: every website.menu / website.page URL the module creates, plus --routes,
     opened as the public user and as admin.
  4. Flow tours (--tour-js / --tour): the clickbot proves pages load; a tour proves the module's key
     flow works (fill a form, save, click the website button, add to cart). --tour-js copies a tour
     file into this smoke module (bundle web.assets_tests); --tour runs a registered tour by name,
     starting on URL (Odoo 20 ignores the tour's own url in tests; default /odoo, or / for public),
     as admin by default, or ":public" / ":<login>". Template: references/tests-and-tours.md.
The generated module lives outside the user's addons (default: a temp dir) and is never shipped.
"""
import argparse
import re
import shutil
import tempfile
from pathlib import Path

MANIFEST = """{{
    'name': 'Migration smoke test for {module}',
    'version': '20.0.1.0.0',
    'depends': ['{module}', 'web', 'web_tour'],
    'author': 'odoo-migrate-to-20',
    'license': 'LGPL-3',
    'installable': True,
    'assets': {{'web.assets_tests': {tour_assets!r}}},
}}
"""

TEST = '''import logging

import odoo.tests

_logger = logging.getLogger(__name__)
MODULE = {module!r}
EXTRA_ROUTES = {routes!r}
TOURS = {tours!r}  # (name, start url, login or None)
WAIT_JS = "setTimeout(() => console.log('test successful'), 2500);"


@odoo.tests.tagged("post_install", "-at_install", "mig20_smoke")
class TestMigrationSmoke(odoo.tests.HttpCase):

    def _module_records(self, model):
        data = self.env["ir.model.data"].search([("module", "=", MODULE), ("model", "=", model)])
        return self.env[model].browse(data.mapped("res_id")).exists(), {{d.res_id: f"{{d.module}}.{{d.name}}" for d in data}}

    def test_01_backend(self):
        if "tour_enabled" in self.env["res.users"]._fields:
            self.env.ref("base.user_admin").tour_enabled = False
        menus, xmlids = self._module_records("ir.ui.menu")
        roots = menus.filtered(lambda m: not m.parent_id)
        for root in roots:
            with self.subTest(app=root.name):
                _logger.info("clickbot on app %s", xmlids[root.id])
                self.browser_js(
                    "/odoo",
                    "odoo.loader.modules.get('@web/webclient/clickbot/clickbot_loader')"
                    ".startClickEverywhere({{ xmlId: '%s', logger: true }});" % xmlids[root.id],
                    "odoo.isReady === true", login="admin", timeout=600,
                    success_signal="clickbot test succeeded",
                )
        others = menus.filtered(lambda m: m.action and not (m.parent_path and any(
            str(r.id) == m.parent_path.split("/")[0] for r in roots)))
        for menu in others:
            action = menu.action
            with self.subTest(menu=menu.complete_name):
                _logger.info("open action of menu %s", menu.complete_name)
                self.browser_js(f"/odoo/action-{{action.id}}", WAIT_JS, "odoo.isReady === true",
                                login="admin", timeout=90)
                if action._name == "ir.actions.act_window" and "form" in (action.view_mode or ""):
                    self.browser_js(f"/odoo/action-{{action.id}}/new", WAIT_JS, "odoo.isReady === true",
                                    login="admin", timeout=90)

    def test_02_website(self):
        urls = set(EXTRA_ROUTES)
        if "website.menu" in self.env:
            wmenus, _ = self._module_records("website.menu")
            urls |= {{m.url for m in wmenus if m.url and m.url.startswith("/")}}
        if "website.page" in self.env:
            pages, _ = self._module_records("website.page")
            urls |= {{p.url for p in pages if p.url}}
        for url in sorted(urls):
            for login in (None, "admin"):
                with self.subTest(url=url, login=login):
                    _logger.info("open %s as %s", url, login or "public")
                    res = self.url_open(url) if login is None else None
                    if res is not None:
                        self.assertLess(res.status_code, 500, f"{{url}} returned {{res.status_code}}")
                    self.browser_js(url, WAIT_JS, login=login, timeout=90)

    def test_03_flow_tours(self):
        for name, url, login in TOURS:
            with self.subTest(tour=name, login=login):
                _logger.info("tour %s from %s as %s", name, url, login or "public")
                self.start_tour(url, name, login=login, timeout=300)
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("module")
    ap.add_argument("--routes", default="", help="comma-separated extra website routes to open")
    ap.add_argument("--tour-js", action="append", default=[], metavar="FILE",
                    help="tour file to ship in the smoke module (registry.category('web_tour.tours').add(...)); repeatable")
    ap.add_argument("--tour", action="append", default=[], metavar="NAME[@URL][:LOGIN]",
                    help="run this registered tour from URL (default /odoo, or / for public) as LOGIN "
                         "(default admin; 'public' for the public user); repeatable")
    ap.add_argument("--out", help="directory to create the smoke module in (default: new temp dir)")
    args = ap.parse_args()

    out = Path(args.out or tempfile.mkdtemp(prefix="mig20_smoke_"))
    name = f"mig20_smoke_{args.module}"
    mod = out / name
    (mod / "tests").mkdir(parents=True, exist_ok=True)
    (mod / "__init__.py").write_text("")
    tour_assets = []
    for f in args.tour_js:
        src = Path(f).resolve()
        if not src.is_file():
            ap.error(f"--tour-js {f}: no such file")
        (mod / "static" / "tests" / "tours").mkdir(parents=True, exist_ok=True)
        shutil.copy(src, mod / "static" / "tests" / "tours" / src.name)
        tour_assets.append(f"{name}/static/tests/tours/{src.name}")
    tours = []
    for t in args.tour:
        m = re.fullmatch(r"([^@:]+)(?:@([^:]*))?(?::([\w.@-]+))?", t)
        if not m:
            ap.error(f"--tour {t}: expected NAME[@URL][:LOGIN]")
        tname, url, login = m.groups()
        login = None if login == "public" else (login or "admin")
        tours.append((tname, url or ("/odoo" if login else "/"), login))
    (mod / "__manifest__.py").write_text(MANIFEST.format(module=args.module, tour_assets=tour_assets))
    (mod / "tests" / "__init__.py").write_text("from . import test_smoke\n")
    routes = [r.strip() for r in args.routes.split(",") if r.strip()]
    (mod / "tests" / "test_smoke.py").write_text(TEST.format(module=args.module, routes=routes, tours=tours))
    print(f"SMOKE_ADDONS={out}")
    print(f"SMOKE_MODULE={name}")


if __name__ == "__main__":
    main()
