#!/usr/bin/env python3
"""Scan an Odoo module for code that breaks or silently misbehaves on Odoo 20.

Usage:
    scan.py <module_dir> [--json] [--area AREA] [--fix-tesc] [--icons]

Severity:
    BLOCKER  install/import fails, or code throws on load
    SILENT   installs but renders nothing / override never called / constraint dropped
    RUNTIME  fails when the code path runs
    WARN     deprecated, works in 20 with a warning, or cosmetic

Exit code: 1 if any BLOCKER or SILENT finding remains, else 0.
"""
import argparse
import ast
import bisect
import json
import re
import sys
from pathlib import Path

PY, XML, JS, SCSS, CSV, MANIFEST = "py", "xml", "js", "scss", "csv", "manifest"

# (id, area, severity, kinds, where, regex, message, reference, auto)
#   where: "any" | "static" (only under static/) | "server" (outside static/)
#   auto: which tool fixes it ("" = manual)
RULES = [
    # ---- manifest / modules ------------------------------------------------
    ("manifest-qweb-key", "manifest", "SILENT", [MANIFEST], "any", r"""['"]qweb['"]\s*:""",
     "manifest 'qweb' key is ignored: move files into assets", "manifest-and-modules.md", ""),
    ("manifest-old-keys", "manifest", "SILENT", [MANIFEST], "any", r"""['"](demo_xml|init_xml|update_xml)['"]\s*:""",
     "ignored manifest key", "manifest-and-modules.md", ""),
    # ---- python / orm ------------------------------------------------------
    ("api-multi-one", "python", "BLOCKER", [PY], "any", r"@api\.(multi|one)\b", "@api.multi/@api.one removed", "python-orm.md", ""),
    ("api-returns", "python", "BLOCKER", [PY], "any", r"@api\.returns\b", "@api.returns removed", "python-orm.md", ""),
    ("api-model-create", "python", "RUNTIME", [PY], "any", r"@api\.model\s*\n\s*def create\(self,\s*vals\b",
     "@api.model create(vals): 20 passes a list -> @api.model_create_multi create(vals_list)", "python-orm.md", ""),
    ("osv-expression", "python", "BLOCKER", [PY], "any", r"\bodoo\.osv\b|from odoo\.osv import|\bexpression\.(AND|OR|normalize_domain|TRUE_DOMAIN|FALSE_DOMAIN)\b",
     "odoo.osv removed -> from odoo.fields import Domain", "python-orm.md", ""),
    ("name-get", "python", "SILENT", [PY], "any", r"def name_get\(", "name_get never called -> _compute_display_name", "python-orm.md", ""),
    ("name-search", "python", "SILENT", [PY], "any", r"def _name_search\(", "_name_search never called -> _search_display_name / _rec_names_search", "python-orm.md", ""),
    ("fields-view-get", "python", "SILENT", [PY], "any", r"\bfields_view_get\b", "fields_view_get removed -> _get_view / get_views", "python-orm.md", ""),
    ("sql-constraints", "python", "SILENT", [PY], "any", r"_sql_constraints\s*=", "_sql_constraints ignored -> models.Constraint/Index", "python-orm.md", "upgrade_code 18.1"),
    ("field-states", "python", "SILENT", [PY], "any", r"\bstates\s*=\s*\{", "field states= ignored -> view readonly= expression", "python-orm.md", ""),
    ("field-old-params", "python", "SILENT", [PY], "any", r"\b(track_visibility|group_operator|digits_compute)\s*=", "obsolete field parameter (tracking= / aggregator= / digits=)", "python-orm.md", ""),
    ("read-group", "python", "RUNTIME", [PY], "any", r"\.read_group\(", "read_group signature changed -> _read_group / formatted_read_group", "python-orm.md", ""),
    ("user-has-groups", "python", "RUNTIME", [PY], "any", r"\buser_has_groups\(", "user_has_groups removed -> env.user.has_group(s)", "python-orm.md", ""),
    ("check-access-old", "python", "RUNTIME", [PY], "any", r"check_access_(rights|rule)\(|_filter_access_rules\(", "-> check_access / has_access / _filtered_access", "python-orm.md", ""),
    ("private-env-props", "python", "WARN", [PY], "any", r"\bself\._(cr|uid|context)\b|\brequest\.(cr|uid|context)\b", "-> self.env.cr/uid/context (request.env.*)", "python-orm.md", "upgrade_code 18.5 (self only)"),
    ("ormcache-old", "python", "BLOCKER", [PY], "any", r"\bormcache_context\b|skiparg\s*=", "ormcache_context / skiparg removed", "python-orm.md", ""),
    ("clear-caches", "python", "RUNTIME", [PY], "any", r"\bclear_caches?\(\)", "-> env.transaction.invalidate_ormcache()", "python-orm.md", ""),
    ("toggle-active", "python", "RUNTIME", [PY], "any", r"\btoggle_active\(|_check_recursion\(|\blazy_property\b", "removed API (action_archive / _has_cycle / cached_property)", "python-orm.md", ""),
    ("tools-removed", "python", "BLOCKER", [PY], "any", r"\bpycompat\b|\bustr\(|odoo\.tools\.query\b|from odoo\.tools import[^\n]*\b(mod10r|street_split|ustr|pycompat)\b",
     "removed odoo.tools helper", "python-orm.md", ""),
    ("odoo-registry", "python", "RUNTIME", [PY], "any", r"\bodoo\.registry\(", "odoo.registry() removed -> Registry(db)", "python-orm.md", ""),
    ("message-post-with", "python", "RUNTIME", [PY], "any", r"message_post_with_(view|template)\(", "-> message_post_with_source", "python-orm.md", ""),
    ("track-hooks", "python", "SILENT", [PY], "any", r"def _track_(subtype|template)\(", "renamed: _track_log_get_default_subtype / _track_template_parameters", "python-orm.md", ""),
    ("test-classes", "python", "BLOCKER", [PY], "any", r"\b(SavepointCase|SingleTransactionCase)\b", "removed test base class -> TransactionCase", "python-orm.md", ""),
    ("py-libs", "python", "BLOCKER", [PY], "any", r"^\s*(import (pytz|xlwt|imp|distutils|pkg_resources)|from (pytz|xlwt|imp|distutils|pkg_resources)\b)",
     "library not available in 20 env / py3.12", "python-orm.md", ""),
    ("ir-property", "python", "RUNTIME", [PY], "any", r"['\"]ir\.property['\"]", "ir.property model removed", "python-orm.md", ""),
    # ---- renamed fields (py + xml + js) -------------------------------------
    ("renamed-groups-id", "renames", "BLOCKER", [PY, XML, JS], "any", r"\bgroups_id\b", "groups_id -> group_ids", "field-model-renames.md", ""),
    ("renamed-group-category", "renames", "BLOCKER", [XML], "server", r"model=\"res\.groups\"[\s\S]{0,400}?name=\"(category_id|users)\"",
     "res.groups category_id -> privilege_id, users -> user_ids", "security-ir-access.md", ""),
    ("renamed-stock-qty", "renames", "BLOCKER", [PY, XML, JS], "any", r"\b(qty_done|quantity_done|reserved_availability|move_lines)\b", "stock field renamed (quantity / move_ids)", "field-model-renames.md", ""),
    ("renamed-detailed-type", "renames", "BLOCKER", [PY, XML, JS], "any", r"\bdetailed_type\b", "detailed_type -> type + is_storable", "field-model-renames.md", ""),
    ("renamed-cron", "renames", "BLOCKER", [XML, PY], "any", r"\b(numbercall|doall)\b", "ir.cron numbercall/doall removed", "field-model-renames.md", ""),
    ("renamed-report-file", "renames", "BLOCKER", [XML, PY], "any", r"name=\"report_file\"|['\"]report_file['\"]", "ir.actions.report report_file removed", "field-model-renames.md", ""),
    ("renamed-line-tax", "renames", "BLOCKER", [PY, XML, JS], "any", r"\btax_id\b|\btaxes_id\b", "sale/purchase line tax_id/taxes_id -> tax_ids (check model!)", "field-model-renames.md", ""),
    ("renamed-product-uom", "renames", "BLOCKER", [PY, XML, JS], "any", r"\bproduct_uom\b(?!_)", "product_uom -> product_uom_id (sale/purchase lines) / uom_id (stock.move)", "field-model-renames.md", ""),
    ("renamed-partner", "renames", "RUNTIME", [PY, XML, JS], "any", r"\b(company_type|address_home_id)\b|name=\"mobile\"|\.mobile\b", "res.partner/hr field removed", "field-model-renames.md", ""),
    ("renamed-analytic", "renames", "BLOCKER", [PY, XML], "any", r"\banalytic_tag_ids\b|\banalytic_account_id\b", "analytic fields -> analytic_distribution (check model)", "field-model-renames.md", ""),
    ("renamed-mail-template", "renames", "BLOCKER", [XML, PY], "any", r"name=\"report_template\"", "report_template -> report_template_ids", "field-model-renames.md", ""),
    # ---- controllers ------------------------------------------------------
    ("route-json", "controllers", "WARN", [PY], "any", r"type\s*=\s*['\"]json['\"]", "type='json' -> 'jsonrpc'", "controllers-http.md", "upgrade_code 18.1 (controllers/ only)"),
    ("http-imports", "controllers", "BLOCKER", [PY], "any", r"from odoo\.http import[^\n]*\b(content_disposition|Stream|STATIC_CACHE|serialize_exception|SessionExpiredException|Session\b|db_list|db_filter|dispatch_rpc|root)\b",
     "name no longer exported by odoo.http -> import from submodule", "controllers-http.md", ""),
    ("web-controllers-main", "controllers", "BLOCKER", [PY], "any", r"odoo\.addons\.web\.controllers\.main\b", "web.controllers.main split", "controllers-http.md", ""),
    ("jsonrequest", "controllers", "RUNTIME", [PY], "any", r"request\.jsonrequest", "-> request.get_json_data()", "controllers-http.md", ""),
    ("request-website", "controllers", "RUNTIME", [PY, XML], "any", r"\brequest\.website\b|get_current_website\(", "request.website removed -> request.env.website", "controllers-http.md", ""),
    ("sale-get-order", "website-sale", "RUNTIME", [PY, XML], "any", r"sale_get_order\(|\b_cart_update\(", "-> request.cart / _cart_add / _cart_update_line_quantity", "website-sale-portal.md", ""),
    ("portal-home-values", "website-sale", "SILENT", [PY], "any", r"def _prepare_home_portal_values\(", "-> _prepare_portal_counter_values + portal.entry records", "website-sale-portal.md", ""),
    # ---- views / xml ------------------------------------------------------
    ("xml-attrs", "views", "BLOCKER", [XML], "server", r"\battrs\s*=\s*\"", "attrs removed -> invisible/readonly/required expressions", "views-xml-data.md", ""),
    ("xml-states", "views", "BLOCKER", [XML], "server", r"<(button|field)\b[^>]*\bstates\s*=\s*\"", "states= removed -> invisible expression", "views-xml-data.md", ""),
    ("xml-tree", "views", "BLOCKER", [XML, PY, JS], "any", r"<tree\b|</tree>|view_mode[^\n]*\btree\b|tree_view_ref|['\"]tree['\"]\s*\)", "tree -> list", "views-xml-data.md", "upgrade_code 17.5"),
    ("xml-search-group-string", "views", "BLOCKER", [XML], "server", r"<search\b(?:(?!</search>)[\s\S])*?<group\b[^>]*\b(string|expand)\s*=",
     "<group string=/expand=> not allowed in a search view (RNG): use plain filters + <separator/>, or <group> without attributes", "views-xml-data.md", ""),
    ("xml-report-tag", "views", "BLOCKER", [XML], "server", r"<(report|act_window)\b", "<report>/<act_window> tags removed", "views-xml-data.md", ""),
    ("xml-oe-chatter", "views", "SILENT", [XML], "server", r"class=\"oe_chatter\"", "oe_chatter div vanishes -> <chatter/>", "views-xml-data.md", ""),
    ("xml-kanban-box", "views", "BLOCKER", [XML], "server", r"t-name=\"kanban-box\"|kanban_image\(|kanban_getcolor", "kanban-box -> card template", "views-xml-data.md", ""),
    ("xml-settings-block", "views", "WARN", [XML], "server", r"app_settings_block|o_setting_box", "old settings layout -> <app>/<block>/<setting>", "views-xml-data.md", ""),
    ("xml-base64", "views", "WARN", [XML], "server", r"type=\"base64\"", "type=base64 -> bytes", "views-xml-data.md", "upgrade_code 19.3"),
    ("xml-widget-renamed", "views", "RUNTIME", [XML], "any", r"widget=\"(remaining_days|selection_badge|many2many_tags_avatar_popover|boolean_toggle_labeled|section_and_note_text|iban)\"", "widget renamed/removed in 20", "backend-js-owl3.md", ""),
    ("xml-removed-layout", "views", "BLOCKER", [XML], "server", r"web\.external_layout_(bold|boxed|striped|background|clean)\b", "report layout removed in 20", "qweb-reports-mail.md", ""),
    ("portal-category-xpath", "website-sale", "BLOCKER", [XML], "server", r"portal_(client|service|vendor|common)_category|portal\.portal_docs_entry", "portal home category divs gone -> portal.entry records", "website-sale-portal.md", ""),
    ("website-sale-removed-tmpl", "website-sale", "BLOCKER", [XML], "server",
     r"inherit_id=\"website_sale\.(cart_popover|cart_summary|short_cart_summary|extra_info_option|payment_footer|payment_sale_note|cart_delivery|payment_delivery|payment_delivery_methods|products_fiscal_position|row_addresses|address_kanban|address_on_payment|address_row|billing_address_row|delivery_address_row|add_to_cart_redirect|products_add_to_cart|product_variants|product_custom_text|product_share_buttons|products_description|products_design_\w+|products_thumb_\w+|product_picture_magnify_\w+|o_wsale_offcanvas_color_attribute|s_add_to_cart_options|add_grid_or_list_option|pricelist_list|products_list_view|product_category_extra_link)\"",
     "inherits a website_sale template removed by 20", "website-sale-portal.md", ""),
    ("website-sale-inherit", "website-sale", "WARN", [XML], "server", r"inherit_id=\"website_sale\.", "website_sale override: re-diff xpaths against the 20 template", "website-sale-portal.md", ""),
    ("website-header-removed", "website", "BLOCKER", [XML, PY], "any", r"website\.(template_header_(centered_logo|contact|hamburger_full|image|magazine|slogan\w*)|option_header_off_canvas\w*|header_search_box_input)\b", "website header template removed", "website-builder-snippets.md", ""),
    ("snippet-options-old", "website", "BLOCKER", [XML, JS], "any", r"website\.snippet_options|snippet_options\"|options\.registry|@web_editor|web_editor\.|data-js=\"|builder_options\s*:|_selector\s*:\s*\[",
     "old snippet options / web_editor / 19 builder_options", "website-builder-snippets.md", ""),
    ("snippet-structure-old", "website", "BLOCKER", [XML], "server", r"snippet_structure'\]/div|hasclass\('o_panel_body'\)|t-thumbnail=", "old snippet panel registration", "website-builder-snippets.md", ""),
    # ---- server qweb -------------------------------------------------------
    ("qweb-tesc", "qweb", "SILENT", [XML], "server", r"\bt-esc\s*=", "t-esc renders NOTHING in 20 -> t-out", "qweb-reports-mail.md", "scan.py --fix-tesc"),
    ("qweb-traw", "qweb", "SILENT", [XML], "server", r"\bt-raw\s*=", "t-raw renders NOTHING in 20 -> t-out (+Markup for trusted html)", "qweb-reports-mail.md", "scan.py --fix-tesc"),
    ("qweb-tcall-tset", "qweb", "SILENT", [XML], "server", r"<t\s+t-call=\"[^\"]+\"\s*>\s*<t\s+t-set=", "t-set in t-call body no longer reaches callee -> attributes", "qweb-reports-mail.md", "upgrade_code 19.1"),
    ("mail-jinja", "qweb", "SILENT", [XML], "server", r"\$\{object\.|^\s*%\s*(if|for|endif|endfor)\b", "Jinja/Mako mail syntax -> qweb / {{ }}", "qweb-reports-mail.md", ""),
    # ---- security ---------------------------------------------------------
    ("secret-in-source", "security", "BLOCKER", [PY, XML, JS, CSV, MANIFEST, SCSS], "any",
     r"\bsk-(proj-)?[A-Za-z0-9_-]{20,}|\bglpat-[A-Za-z0-9_.-]{20,}|\bgh[pousr]_[A-Za-z0-9]{30,}|\bAKIA[0-9A-Z]{16}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bxox[baprs]-[A-Za-z0-9-]{10,}",
     "credential/API key in source: remove it from the migrated copy and tell the user to revoke it", "security-ir-access.md", ""),
    ("acl-csv", "security", "BLOCKER", [CSV], "any", r"^id,", "ir.model.access.csv -> security/ir.access.csv", "security-ir-access.md", "upgrade_code 19.4"),
    ("acl-xml", "security", "BLOCKER", [XML], "server", r"model=\"(ir\.model\.access|ir\.rule)\"", "ir.model.access / ir.rule records -> ir.access", "security-ir-access.md", "upgrade_code 19.4"),
    # ---- backend js / owl --------------------------------------------------
    ("owl-static-props", "backend-js", "BLOCKER", [JS], "static", r"static\s+(props|defaultProps)\s*=", "static props THROWS in Owl 3 -> props = useProps({...})", "backend-js-owl3.md", ""),
    ("owl-removed-hooks", "backend-js", "BLOCKER", [JS], "static", r"\b(useState|useRef|useExternalListener|useChildSubEnv|onRendered)\s*\(", "Owl 2 hook removed (proxy / signal.ref / useListener)", "backend-js-owl3.md", "owl3 (partial)"),
    ("owl-bad-compat-import", "backend-js", "BLOCKER", [JS], "static", r"import\s*\{[^}]*\b(useRef|useExternalListener|useComponent|onRendered|useChildSubEnv)\b[^}]*\}\s*from\s*[\"']@web/owl2/utils[\"']",
     "owl3 script bug: @web/owl2/utils does not export this", "upgrade-code-tool.md", ""),
    ("owl-custom-directive", "backend-js", "BLOCKER", [XML, JS], "static", r"t-custom-(ref|model)\b", "t-custom-ref/model undefined in 20 -> signal.ref()/signal()", "upgrade-code-tool.md", ""),
    ("owl-tmodel-tref", "backend-js", "RUNTIME", [XML, JS], "static", r"t-(model|ref)=\"(?!this\.)", "t-model/t-ref must target a signal on this", "backend-js-owl3.md", ""),
    ("owl-env-debug", "backend-js", "BLOCKER", [JS, XML], "static", r"env\.(debug|isSmall)\b", "env.debug / env.isSmall throw in 20", "backend-js-owl3.md", ""),
    ("owl-input-refname", "backend-js", "RUNTIME", [JS], "static", r"\brefName\s*:", "useInputField needs ref: signal", "backend-js-owl3.md", ""),
    ("js-odoo-define", "backend-js", "BLOCKER", [JS], "static", r"odoo\.define\s*\(", "odoo.define legacy module -> ES module rewrite", "backend-js-owl3.md", ""),
    ("js-legacy-widget", "backend-js", "BLOCKER", [JS], "static", r"\b(Widget\.extend|AbstractField|AbstractAction|AbstractController|AbstractRenderer|BasicModel|FieldRegistry|\.include\(\{)|require\(\s*['\"]web\.", "legacy widget framework removed", "backend-js-owl3.md", ""),
    ("js-patch-3arg", "backend-js", "BLOCKER", [JS], "static", r"\bpatch\(\s*[\w.]+\s*,\s*[\"']", "3-arg patch throws since 17", "backend-js-owl3.md", ""),
    ("js-old-services", "backend-js", "RUNTIME", [JS], "static", r"useService\(\s*[\"'](rpc|user|company)[\"']\s*\)|\b_lt\(|rpc_service", "service removed -> rpc / user imports", "backend-js-owl3.md", ""),
    ("js-owl-global", "backend-js", "BLOCKER", [JS], "static", r"=\s*owl\s*;|owl\.(Component|hooks|tags)\b", "global owl destructuring -> import from @odoo/owl", "backend-js-owl3.md", ""),
    ("js-kanban-widget", "backend-js", "SILENT", [JS], "static", r"\.add\(\s*[\"']kanban\.", "kanban.* field widget ignored in 20 -> card.*", "backend-js-owl3.md", ""),
    ("tmpl-owl1", "backend-js", "WARN", [XML], "static", r"owl=\"1\"", "owl=\"1\" obsolete", "backend-js-owl3.md", ""),
    ("tmpl-tesc-static", "backend-js", "WARN", [XML, JS], "static", r"\bt-(esc|raw)\s*=", "t-esc/t-raw in Owl template -> t-out", "backend-js-owl3.md", "owl3 (t-esc)"),
    ("tmpl-tslot-portal", "backend-js", "WARN", [XML, JS], "static", r"\bt-(slot|portal)\s*=", "t-slot -> t-call-slot, t-portal -> Portal", "backend-js-owl3.md", "owl3"),
    ("qunit-tests", "backend-js", "WARN", [JS], "static", r"QUnit\.(module|test)|web\.qunit_suite_tests", "QUnit removed in 20 (Hoot)", "backend-js-owl3.md", ""),
    # ---- website / public js ----------------------------------------------
    ("public-widget", "website-js", "BLOCKER", [JS], "static", r"publicWidget|public_widget|web\.public\.widget", "publicWidget removed -> Interaction", "website-interactions.md", ""),
    ("jquery", "website-js", "BLOCKER", [JS], "static", r"(?<![\w$])\$\(|\bjQuery\b|\.\$el\b|\$target\b|\$\.ajax|\$\.fn\b", "jQuery removed in 20", "website-interactions.md", ""),
    ("frontend-rpc", "website-js", "BLOCKER", [JS], "static", r"web\.ajax|ajax\.jsonRpc|this\._rpc\(|\btrigger_up\(", "legacy rpc/event bus -> rpc() / CustomEvent", "website-interactions.md", ""),
    # ---- assets / scss / icons --------------------------------------------
    ("assets-removed-bundle", "assets", "BLOCKER", [MANIFEST, XML], "any", r"web\.assets_(common|qweb)\b|web\._assets_jquery|web\.qunit_suite_tests|website\.assets_(all_wysiwyg|wysiwyg_inside)|web_editor\.assets", "asset bundle removed", "backend-js-owl3.md", ""),
    ("assets-xml-inherit", "assets", "SILENT", [XML], "server", r"inherit_id=\"(web|website|point_of_sale)\.assets_", "XML asset template inherit -> manifest assets", "backend-js-owl3.md", ""),
    ("bs4-classes", "scss", "WARN", [XML, JS, SCSS], "any", r"data-(toggle|target|dismiss|ride|slide)=|\b(ml|mr|pl|pr)-(sm-|md-|lg-|xl-)?[0-5]\b|\bfloat-(left|right)\b|\btext-(left|right)\b|\bform-group\b|\bcustom-(select|control|checkbox)\b|\bbadge-(primary|secondary|success|danger|warning|info|light|dark|pill)\b|\bsr-only\b|\bbtn-block\b|\bno-gutters\b|\bfont-weight-\w+|\bform-row\b|\bjumbotron\b|\bcard-deck\b",
     "Bootstrap 4 class/attribute", "scss-bootstrap-icons.md", ""),
    ("fa-icons", "scss", "WARN", [XML, JS, SCSS, PY], "any", r"\bfa fa-[\w-]+|icon=\"fa-[\w-]+\"|['\"]fa-[\w-]+['\"]", "Font Awesome removed in 20 -> oi/Material Symbols", "scss-bootstrap-icons.md", ""),
    ("scss-removed-vars", "scss", "BLOCKER", [SCSS], "any", r"\$o-social-colors", "SCSS variable removed in 20", "scss-bootstrap-icons.md", ""),
]

def _load_config():
    """Resolve paths through env.sh (config file + auto-detection), so scan.py and the shell scripts agree."""
    import os
    import subprocess
    keys = ["ODOO20_SERVER", "ODOO20_ENTERPRISE", "ODOO20_PYTHON"]
    env_sh = Path(__file__).with_name("env.sh")
    try:
        out = subprocess.run(["bash", "-c", f'source "{env_sh}" >/dev/null 2>&1; ' + "; ".join(f'echo "${k}"' for k in keys)],
                             capture_output=True, text=True, timeout=60).stdout.splitlines()
    except Exception:  # noqa: BLE001
        out = []
    cfg = dict(zip(keys, out + [""] * len(keys)))
    for k in keys:
        cfg[k] = os.environ.get(k) or cfg.get(k, "")
    return cfg


CFG = _load_config()
SERVER20 = Path(CFG["ODOO20_SERVER"]) if CFG["ODOO20_SERVER"] else None
ENTERPRISE20 = Path(CFG["ODOO20_ENTERPRISE"]) if CFG["ODOO20_ENTERPRISE"] else None
PY20 = CFG["ODOO20_PYTHON"]
CORE20_ADDONS = [p for p in ([p for p in ([SERVER20 / "addons", SERVER20 / "odoo" / "addons"] if SERVER20 else []) + ([ENTERPRISE20] if ENTERPRISE20 else [])]) if p.is_dir()]
CORE_PY_DIRS = [p for p in ([SERVER20 / "odoo", SERVER20 / "addons"] if SERVER20 else []) + ([ENTERPRISE20] if ENTERPRISE20 else [])]


TEXT_EXT = {".py": PY, ".xml": XML, ".js": JS, ".scss": SCSS, ".css": SCSS, ".csv": CSV}
SEVERITY_ORDER = {"BLOCKER": 0, "SILENT": 1, "RUNTIME": 2, "WARN": 3}


def file_kind(path: Path):
    if path.name == "__manifest__.py":
        return MANIFEST
    if path.suffix == ".csv" and path.name != "ir.model.access.csv":
        return None
    return TEXT_EXT.get(path.suffix)


def iter_files(module: Path):
    for path in sorted(module.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or "node_modules" in path.parts:
            continue
        rel = path.relative_to(module)
        if rel.parts[:2] == ("static", "lib"):  # vendored libraries
            continue
        if file_kind(path):
            yield path


def manifest_checks(module: Path):
    findings = []
    mpath = module / "__manifest__.py"
    if not mpath.exists():
        return [dict(rule="no-manifest", area="manifest", severity="BLOCKER", file="__manifest__.py", line=0,
                     text="", message="no __manifest__.py", ref="manifest-and-modules.md", auto="")]
    try:
        manifest = ast.literal_eval(mpath.read_text())
    except Exception as e:  # noqa: BLE001
        return [dict(rule="manifest-parse", area="manifest", severity="BLOCKER", file="__manifest__.py", line=0,
                     text=str(e), message="manifest is not a literal dict", ref="manifest-and-modules.md", auto="")]
    version = str(manifest.get("version", ""))
    parts = version.split(".")
    if not (len(parts) >= 4 and parts[0] == "20") and not (2 <= len(parts) <= 3 and version):
        findings.append(("manifest-version", "BLOCKER", f"version '{version}' -> '20.0.x.y.z' (else module silently uninstallable)"))
    elif 2 <= len(parts) <= 3:
        findings.append(("manifest-version", "WARN", f"version '{version}' gets 20.0. prefixed; write it explicitly"))
    if "license" not in manifest:
        findings.append(("manifest-license", "WARN", "no license key (defaults to LGPL-3)"))
    search = CORE20_ADDONS
    siblings = module.parent
    for dep in manifest.get("depends", []) if search else []:
        if not any((p / dep / "__manifest__.py").exists() for p in search):
            where = "custom module: migrate it first" if (siblings / dep / "__manifest__.py").exists() else \
                "not in Odoo 20 core/enterprise: removed/merged or third-party (see manifest-and-modules.md)"
            findings.append((f"depends-{dep}", "BLOCKER", f"depends '{dep}': {where}"))
    for key in ("data", "demo"):
        for f in manifest.get(key, []):
            if not (module / f).exists():
                findings.append((f"missing-{key}", "BLOCKER", f"{key} file listed but missing: {f}"))
    for bundle, items in (manifest.get("assets") or {}).items():
        for item in items:
            paths = [item] if isinstance(item, str) else [p for p in item[1:] if isinstance(p, str)]
            for p in paths:
                if p.startswith(("http://", "https://")) or "*" in p or "/" not in p:
                    continue
                mod, _, rest = p.partition("/")
                if mod == module.name and not (module / rest).exists():
                    findings.append(("missing-asset", "BLOCKER", f"asset in {bundle} missing on disk: {p}"))
            if isinstance(item, str) and item.startswith(("http://", "https://")):
                findings.append(("external-asset", "WARN", f"external URL in {bundle}: {item} (vendor under static/lib/)"))
    return [dict(rule=r, area="manifest", severity=s, file="__manifest__.py", line=0, text="", message=m,
                 ref="manifest-and-modules.md", auto="") for r, s, m in findings]


STDLIB = set(getattr(sys, "stdlib_module_names", ()))


def python_import_checks(module: Path):
    """Third-party imports that the Odoo 20 venv cannot import (install blocker)."""
    import subprocess
    names = {}
    for path in module.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(errors="replace"))
        except SyntaxError as e:
            names.setdefault("__syntax__", []).append((path, e.lineno or 0, str(e)))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module]
            else:
                continue
            for m in mods:
                top = m.split(".")[0]
                if top in STDLIB or top in ("odoo", "__future__") or (module.parent / top).exists():
                    continue
                names.setdefault(top, []).append((path, node.lineno, m))
    findings = []
    for path, line, msg in names.pop("__syntax__", []):
        findings.append(dict(rule="py-syntax", area="python", severity="BLOCKER", file=str(path.relative_to(module)),
                             line=line, text="", message=f"syntax error: {msg}", ref="python-orm.md", auto=""))
    if not names or not PY20 or not Path(PY20).exists():
        return findings
    code = "import importlib.util,sys\nfor n in sys.argv[1:]:\n    print(n, importlib.util.find_spec(n) is not None)"
    out = subprocess.run([PY20, "-c", code, *names], capture_output=True, text=True).stdout.split()
    ok = dict(zip(out[::2], out[1::2]))
    for top, uses in sorted(names.items()):
        if ok.get(top) == "True":
            continue
        path, line, full = uses[0]
        findings.append(dict(rule="py-missing-lib", area="python", severity="BLOCKER",
                             file=str(path.relative_to(module)), line=line, text=f"import {full}",
                             message=f"'{top}' not importable in {PY20} ({len(uses)} use(s)): pip install it into the "
                                     "Odoo 20 venv and declare it in external_dependencies, or port the code",
                             ref="python-orm.md", auto=""))
    return findings


def override_signature_checks(module: Path):
    """Methods overriding an Odoo 20 core method with a different positional signature."""
    import subprocess
    findings = []
    if not CORE_PY_DIRS:
        return findings
    for path in module.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(errors="replace"))
        except SyntaxError:
            continue
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            inherits = []
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign) and any(getattr(t, "id", "") == "_inherit" for t in stmt.targets):
                    try:
                        v = ast.literal_eval(stmt.value)
                    except Exception:  # noqa: BLE001
                        continue
                    inherits = [v] if isinstance(v, str) else list(v)
            if not inherits:
                continue
            for fn in [b for b in cls.body if isinstance(b, ast.FunctionDef)]:
                if fn.name.startswith("__"):
                    continue
                ours = [a.arg for a in fn.args.posonlyargs + fn.args.args]
                cmd = ["grep", "-rn", "--include=*.py", "-E", rf"^\s+def {re.escape(fn.name)}\(", *map(str, CORE_PY_DIRS)]
                hits = subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()
                if not hits:
                    if fn.name.startswith("_") and not any(fn.name.startswith(p) for p in ("_compute_", "_inverse_", "_search_", "_onchange_", "_check_", "_get_", "_prepare_", "_default_")):
                        findings.append(dict(rule="override-gone", area="python", severity="WARN",
                                             file=str(path.relative_to(module)), line=fn.lineno, text=f"def {fn.name}",
                                             message=f"'{fn.name}' is not defined anywhere in Odoo 20: if it overrode a core hook, that hook was renamed/removed (override never called)",
                                             ref="python-orm.md", auto=""))
                    continue
                sigs = set()
                for h in hits[:40]:
                    m = re.search(rf"def {re.escape(fn.name)}\((.*)", h)
                    if not m or ")" not in m.group(1):
                        continue  # multi-line definition: signature not comparable from one line, skip it
                    params = []
                    for p in m.group(1).split(")")[0].split(","):
                        p = p.strip().split(":")[0].split("=")[0].strip()
                        if p.startswith("*"):
                            break  # keyword-only / varargs from here on: not positional
                        if p and p != "/":
                            params.append(p)
                    sigs.add(tuple(params))
                ours_t = tuple(ours)
                if sigs and len(ours_t) not in {len(s) for s in sigs}:
                    best = min(sigs, key=lambda s: abs(len(s) - len(ours_t)))
                    if True:
                        findings.append(dict(rule="override-signature", area="python", severity="RUNTIME",
                                             file=str(path.relative_to(module)), line=fn.lineno,
                                             text=f"def {fn.name}({', '.join(ours)})",
                                             message=f"Odoo 20 defines {fn.name}({', '.join(best)}): align the override signature and super() call",
                                             ref="python-orm.md", auto=""))
    return findings


XMLID_RX = re.compile(
    r"""(?:\bref|inherit_id|action|t-call|parent|groups|t-snippet)\s*=\s*"([^"]+)"|ref\(\s*['"]([a-z0-9_]+\.[\w.]+)['"]\s*\)|\bid\s*=\s*"([a-z0-9_]+\.[\w]+)\"""")
_XMLID_CACHE = {}


def _module_dir20(mod):
    for base in CORE20_ADDONS:
        if (base / mod / "__manifest__.py").exists():
            return base / mod
    return None


def _xmlid_exists(mod, name):
    """True/False, or None when the module itself is not in Odoo 20 (the depends check reports that)."""
    import subprocess
    key = (mod, name)
    if key not in _XMLID_CACHE:
        d = _module_dir20(mod)
        if d is None:
            _XMLID_CACHE[key] = None
        elif name.startswith(("model_", "field_", "module_", "access_")):
            _XMLID_CACHE[key] = True  # generated xmlids
        else:
            pat = rf'id="({re.escape(mod)}\.)?{re.escape(name)}"|^{re.escape(name)},'
            r = subprocess.run(["grep", "-rlE", "--include=*.xml", "--include=*.csv", pat, str(d)], capture_output=True, text=True)
            ok = bool(r.stdout.strip())
            if not ok:  # defined with its full name by another module (e.g. base.default_website lives in website)
                roots = [str(p) for p in CORE20_ADDONS]
                r = subprocess.run(["grep", "-rlE", "--include=*.xml", "--include=*.csv",
                                    rf'id="{re.escape(mod)}\.{re.escape(name)}"|^{re.escape(mod)}\.{re.escape(name)},', *roots],
                                   capture_output=True, text=True)
                ok = bool(r.stdout.strip())
            _XMLID_CACHE[key] = ok
    return _XMLID_CACHE[key]


def xmlid_checks(module: Path):
    """External xmlids (other modules) referenced by this module's XML that do not exist in Odoo 20."""
    findings, seen = [], set()
    for path in sorted(module.rglob("*.xml")):
        if path.relative_to(module).parts[0] == "static":
            continue
        for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            for m in XMLID_RX.finditer(line):
                raw = next(g for g in m.groups() if g)
                for ref in raw.split(","):
                    ref = ref.strip()
                    if not re.fullmatch(r"[a-z0-9_]+\.[a-zA-Z0-9_.]+", ref):
                        continue
                    mod, _, name = ref.partition(".")
                    if mod == module.name or (module.parent / mod).exists():
                        continue
                    if (ref, path) in seen:
                        continue
                    seen.add((ref, path))
                    if _xmlid_exists(mod, name) is False:
                        findings.append(dict(rule="xmlid-missing", area="views", severity="BLOCKER",
                                             file=str(path.relative_to(module)), line=i, text=line.strip()[:160],
                                             message=f"'{ref}' does not exist in Odoo 20 (renamed/removed): find its replacement in the 20 module",
                                             ref="views-xml-data.md", auto=""))
    return findings


def identity_checked_calls(module: Path):
    """Calls to core methods decorated with @check_identity in Odoo 20: from server code they return an
    identity-check action (or raise outside HTTP) instead of doing the work."""
    import subprocess
    if not CORE_PY_DIRS:
        return []
    out = subprocess.run(["grep", "-rn", "-A3", "--include=*.py", "@check_identity", *map(str, CORE_PY_DIRS)],
                         capture_output=True, text=True).stdout
    names = set(re.findall(r"def (\w+)\(", out))
    if not names:
        return []
    rx = re.compile(r"\.(" + "|".join(sorted(names)) + r")\(")
    findings = []
    for path in module.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            m = rx.search(line)
            if m and not line.lstrip().startswith(("def ", "#")):
                findings.append(dict(rule="identity-checked-call", area="python", severity="RUNTIME",
                                     file=str(path.relative_to(module)), line=i, text=line.strip()[:160],
                                     message=f"{m.group(1)}() is @check_identity in Odoo 20: called from code it returns an identity popup "
                                             "action and does nothing (or raises outside HTTP). Use the underlying API (e.g. write 'password' / _change_password)",
                                     ref="python-orm.md", auto=""))
    return findings


def scan(module: Path, area=None):
    findings = (manifest_checks(module) + python_import_checks(module)
                + override_signature_checks(module) + xmlid_checks(module) + identity_checked_calls(module))
    compiled = [(r, re.compile(r[5], re.M)) for r in RULES]
    for path in iter_files(module):
        kind = file_kind(path)
        rel = path.relative_to(module)
        in_static = rel.parts[0] == "static"
        try:
            content = path.read_text(errors="replace")
        except OSError:
            continue
        line_starts = [0] + [m.end() for m in re.finditer(r"\n", content)]
        lines = content.splitlines()
        for rule, rx in compiled:
            rid, rarea, sev, kinds, where, _, msg, ref, auto = rule
            if area and rarea != area:
                continue
            if kind not in kinds:
                continue
            if where == "static" and not in_static or where == "server" and in_static:
                continue
            if rid == "acl-csv" and path.name != "ir.model.access.csv":
                continue
            for m in rx.finditer(content):
                lineno = bisect.bisect_right(line_starts, m.start())
                line = lines[lineno - 1].strip() if lineno - 1 < len(lines) else ""
                findings.append(dict(rule=rid, area=rarea, severity=sev, file=str(rel), line=lineno,
                                     text=line[:160], message=msg, ref=ref, auto=auto))
    if area:
        findings = [f for f in findings if f["area"] == area]
    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["area"], f["file"], f["line"]))
    return findings


def fix_tesc(module: Path):
    """Mechanical t-esc/t-raw -> t-out in every XML file (server and static)."""
    changed = []
    for path in module.rglob("*.xml"):
        if "static/lib" in str(path):
            continue
        text = path.read_text()
        new = re.sub(r"\bt-(esc|raw)(\s*=)", r"t-out\2", text)
        if new != text:
            path.write_text(new)
            changed.append(str(path.relative_to(module)))
    return changed


def fa_icons(module: Path):
    names = {}
    for path in iter_files(module):
        for m in re.finditer(r"\bfa-([a-z0-9-]+)", path.read_text(errors="replace")):
            n = m.group(1)
            if n in {"fw", "lg", "2x", "3x", "4x", "5x", "spin", "pulse", "stack", "inverse", "border", "li", "ul"}:
                continue
            names[n] = names.get(n, 0) + 1
    wishlist = SERVER20 / "addons/web/tooling/icons/icons_wishlist.txt" if SERVER20 else None
    available = set(wishlist.read_text().split()) if wishlist and wishlist.exists() else set()
    return names, available


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("module")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--area")
    ap.add_argument("--fix-tesc", action="store_true", help="rewrite t-esc/t-raw to t-out, then scan")
    ap.add_argument("--icons", action="store_true", help="list fa-* icon names used and exit")
    ap.add_argument("--summary", action="store_true", help="counts only")
    args = ap.parse_args()
    module = Path(args.module).resolve()

    if args.icons:
        names, available = fa_icons(module)
        for n, c in sorted(names.items(), key=lambda x: -x[1]):
            print(f"{c:4d}  fa-{n}")
        if not available:
            print("(ODOO20_SERVER not configured: cannot list the available icon names)")
        print(f"\n{len(names)} distinct fa icons; pick replacements from {len(available)} names in icons_wishlist.txt")
        return 0
    if args.fix_tesc:
        for f in fix_tesc(module):
            print(f"t-out: {f}")

    findings = scan(module, args.area)
    if args.json:
        print(json.dumps(findings, indent=1))
    else:
        counts = {}
        for f in findings:
            counts.setdefault(f["severity"], {}).setdefault(f["area"], 0)
            counts[f["severity"]][f["area"]] += 1
        if not args.summary:
            cur = None
            for f in findings:
                key = (f["severity"], f["area"])
                if key != cur:
                    print(f"\n== {f['severity']} / {f['area']}")
                    cur = key
                auto = f"  [auto: {f['auto']}]" if f["auto"] else ""
                loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
                print(f"  {loc}  {f['rule']}: {f['message']}{auto}")
                if f["text"]:
                    print(f"      {f['text']}")
        print("\nSUMMARY " + module.name)
        for sev in sorted(counts, key=SEVERITY_ORDER.get):
            print(f"  {sev:8s} " + ", ".join(f"{a}={n}" for a, n in sorted(counts[sev].items())))
        if not findings:
            print("  clean")
    return 1 if any(f["severity"] in ("BLOCKER", "SILENT") for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
