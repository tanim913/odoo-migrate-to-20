#!/bin/bash
# Run Odoo 20's upgrade_code scripts on ONE module, safely:
#  - standalone mode (never through odoo-bin, which would also rewrite core addons)
#  - one --script at a time (--from with core on the path crashes in the l10n scripts)
#  - ir-access with core+enterprise on the addons path but --glob limited to the module
#  - owl3-migration explicitly (never selected by --from)
# Verifies afterwards that the Odoo 20 community and enterprise trees are untouched.
#
#   run_upgrade_code.sh <module_dir> <from_version>      e.g. ... $MIG20_TARGET_ROOT/proj/mod 16.0
set -uo pipefail
source "$(dirname "$0")/env.sh"
mig20_require

MOD_DIR=$(realpath "${1:?module dir}")
FROM=${2:?from version, e.g. 16.0}
ADDONS=$(dirname "$MOD_DIR")
MODULE=$(basename "$MOD_DIR")
SERVER=$ODOO20_SERVER
ENT=$ODOO20_ENTERPRISE
PY=$ODOO20_PYTHON
CORE_PATHS=$MIG20_CORE_ADDONS

STAMP=$(mktemp)   # reference time for non-git core trees (nothing is ever written inside core)
core_state() {  # git status when available, else files modified since STAMP
    for d in "$SERVER" ${ENT:+"$ENT"}; do
        git -C "$d" status --porcelain 2>/dev/null || find "$d" -newer "$STAMP" -type f 2>/dev/null | head -50
    done
}
BEFORE=$(core_state)

# version-prefix -> script, in execution order (l10n/account scripts deliberately excluded)
SCRIPTS=(
  "17.5 17.5-01-tree-to-list"
  "18.1 18.1-00-sql-constraint"
  "18.1 18.1-02-route-jsonrpc"
  "18.5 18.5-00-deprecated-properties"
  "18.5 18.5-00-domain-dynamic-dates"
  "19.1 19.1-00-t-call"
  "19.3 19.3-00-base64-in-xml"
  "19.4 19.4-00-ir-access"
  "19.4 19.4-00-ormcache-on-transaction"
  "19.5 19.5-00-tuple-rec_names_search"
)
case "$MODULE" in l10n_*)
  SCRIPTS+=("18.2 18.2-00-l10n-translate" "18.3 18.3-00-l10n-fiscal-position-taxes" "18.5 18.5-00-no-tax-tag-invert" "19.3 19.3-00-account-groups" "19.3 19.3-00-account-report-foldable");;
esac

vlt() { python3 -c "import sys;a,b=(tuple(int(x) for x in s.split('.')[:2]) for s in sys.argv[1:]);sys.exit(0 if a<b else 1)" "$1" "$2"; }

run() {  # run <script> <addons_path> [glob]
    local glob=${3:-"$MODULE/**/*"}
    (cd "$SERVER" && PYTHONPATH="$SERVER" "$PY" odoo/cli/upgrade_code.py --script "$1" \
        --addons-path="$2" --glob "$glob" 2>&1)
}

for entry in "${SCRIPTS[@]}"; do
    ver=${entry%% *}; script=${entry#* }
    vlt "$FROM" "$ver" || continue          # only scripts newer than the source version
    echo "== $script"
    if [ "$script" = "19.4-00-ir-access" ]; then
        run "$script" "$ADDONS,$CORE_PATHS"
    else
        run "$script" "$ADDONS"
    fi
done

if [ -d "$MOD_DIR/static" ]; then
    echo "== owl3-migration"
    run owl3-migration "$ADDONS"
fi

AFTER=$(core_state)
if [ "$BEFORE" != "$AFTER" ]; then
    echo "FATAL: core or enterprise tree changed during upgrade_code. Inspect: git -C $SERVER status${ENT:+ ; git -C $ENT status}" >&2
    exit 3
fi
rm -f "$STAMP"
echo "OK: core and enterprise untouched"
echo "NEXT: review the WARNING/ERROR lines above (ir-access especially), then run scan.py"
