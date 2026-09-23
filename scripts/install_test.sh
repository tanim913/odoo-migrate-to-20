#!/bin/bash
# Install a migrated module on a throwaway Odoo 20 database and report problems.
# Connection settings come from env.sh (ODOO20_CONF / MIG20_DB_*).
#
#   install_test.sh <addons_dir> <module[,module2]> [--tests] [--keep] [--extra-addons DIR] [--db NAME]
#
#   --tests          also run the module's tests (--test-enable --test-tags /<module>)
#   --keep           keep the database afterwards (default: dropped, with its filestore)
#   --extra-addons   additional addons dir (e.g. the smoke-test module dir)
#   --db NAME        reuse/force a database name (implies the caller manages it)
#
# Exit: 0 clean, 1 problems found. Full log path is printed.
set -uo pipefail
source "$(dirname "$0")/env.sh"
mig20_require

ADDONS=$(realpath "${1:?addons dir}")
MODULES=${2:?module(s)}
shift 2
TESTS=0; KEEP=0; EXTRA=""; DB=""
while [ $# -gt 0 ]; do
    case "$1" in
        --tests) TESTS=1;;
        --keep) KEEP=1;;
        --extra-addons) EXTRA=",$(realpath "$2")"; shift;;
        --db) DB=$2; shift;;
    esac
    shift
done

SERVER=$ODOO20_SERVER
PY=$ODOO20_PYTHON
PORT=$MIG20_HTTP_PORT
FIRST=${MODULES%%,*}
DB=${DB:-mig20_${FIRST}_$(date +%H%M%S)}
LOGDIR="$ADDONS/.migration"
[ -d "$LOGDIR" ] || LOGDIR=${TMPDIR:-/tmp}
LOG="$LOGDIR/install_${FIRST}_$(date +%Y%m%d_%H%M%S).log"
DATA_DIR=$MIG20_DATA_DIR          # explicit filestore location (some editors/sandboxes change XDG vars)

ARGS=("${MIG20_ODOO_DB_ARGS[@]}"
      --addons-path="$MIG20_CORE_ADDONS,$ADDONS$EXTRA"
      --data-dir="$DATA_DIR" -d "$DB" -i "$MODULES" --stop-after-init
      --http-port="$PORT" --log-level=info)
if [ $TESTS = 1 ]; then
    TAGS=$(echo "$MODULES" | sed 's#\([^,]*\)#/\1#g')
    ARGS+=(--with-demo --test-enable --test-tags "$TAGS")
fi

echo "DB=$DB  LOG=$LOG"
(cd "$(dirname "$SERVER")" && "$PY" "$SERVER/odoo-bin" "${ARGS[@]}") > "$LOG" 2>&1
RC=$?

# What counts as a problem. Ignore known-noise warnings from core/env.
PROBLEMS=$(grep -nE " (ERROR|CRITICAL) |Traceback|Unknown directives|incompatible version|not installable|Some modules are not loaded|invalid addons directory '$ADDONS|FAIL:|ERROR:|[1-9][0-9]* failed, |, [1-9][0-9]* error\(s\)|skipped.*(websocket|Chrome|browser)|websocket-client module is not installed|Chrome.*not found|Failed to load|ParseError|ValidationError|Element .* cannot be located" "$LOG" \
    | grep -vE "odoo20_custom_addons.*invalid addons directory" || true)
WARNINGS=$(grep -nE " WARNING " "$LOG" | grep -E "$(echo "$MODULES" | tr ',' '|')|deprecated|Deprecat" \
    | grep -vE "Postgres version|http_interface" || true)
STATE=$(psql "${MIG20_PG_ARGS[@]}" -d "$DB" -Atc "select name||'='||state from ir_module_module where name in ('$(echo "$MODULES" | sed "s/,/','/g")')" 2>/dev/null)

echo "== module state: ${STATE:-<db not created>}"
if [ -n "$PROBLEMS" ]; then echo "== PROBLEMS"; echo "$PROBLEMS" | cut -c1-400 | head -80; fi
if [ -n "$WARNINGS" ]; then echo "== WARNINGS (module / deprecation)"; echo "$WARNINGS" | cut -c1-300 | head -60; fi
# Show the traceback tail around the first error for quick diagnosis
FIRST_ERR=$(grep -nE "Traceback|ParseError|ValidationError" "$LOG" | head -1 | cut -d: -f1)
if [ -n "$FIRST_ERR" ]; then
    echo "== first error context"
    sed -n "${FIRST_ERR},$((FIRST_ERR+40))p" "$LOG" | cut -c1-300
fi

if [ $KEEP = 0 ]; then
    dropdb "${MIG20_PG_ARGS[@]}" --if-exists "$DB" 2>/dev/null
    rm -rf "$DATA_DIR/filestore/$DB"
    echo "== dropped $DB"
else
    echo "== kept $DB (drop later: dropdb ${MIG20_PG_ARGS[*]} $DB; rm -rf $DATA_DIR/filestore/$DB)"
fi

ALL_INSTALLED=1
for m in $(echo "$MODULES" | tr ',' ' '); do echo "$STATE" | grep -q "^$m=installed$" || ALL_INSTALLED=0; done
if [ $RC -eq 0 ] && [ -z "$PROBLEMS" ] && [ $ALL_INSTALLED = 1 ]; then
    echo "RESULT: CLEAN"; exit 0
fi
echo "RESULT: FAILED (rc=$RC)"; exit 1
