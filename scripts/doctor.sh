#!/bin/bash
# Check that this machine can run the odoo-migrate-to-20 workflow, show the resolved configuration,
# and optionally save it.
#
#   doctor.sh [--write] [KEY=VALUE ...]
#
#   KEY=VALUE  override a setting for this run (e.g. ODOO20_CONF=~/odoo20.conf MIG20_DB_PORT=5432)
#   --write    save the resolved settings to ${XDG_CONFIG_HOME:-~/.config}/odoo-migrate-to-20/config.env
#
# Exit: 0 when every REQUIRED check passes (optional ones only warn).
WRITE=0
for a in "$@"; do
    case "$a" in
        --write) WRITE=1;;
        *=*) export "${a%%=*}=${a#*=}";;
    esac
done
# shellcheck source=env.sh
source "$(dirname "$0")/env.sh"

FAIL=0
ok()   { printf '  \033[32mOK\033[0m    %s\n' "$*"; }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$*"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; FAIL=1; }

echo "Configuration${MIG20_CONFIG_FILE:+ (from $MIG20_CONFIG_FILE + auto-detection)}:"
for v in ODOO20_SERVER ODOO20_ENTERPRISE ODOO20_PYTHON ODOO20_CONF MIG20_DB_HOST MIG20_DB_PORT MIG20_DB_USER MIG20_TARGET_ROOT MIG20_HTTP_PORT MIG20_DATA_DIR MIG20_OLD_SOURCES; do
    printf '  %-18s %s\n' "$v" "${!v:-<unset>}"
done
echo
echo "Checks:"

# Odoo 20 source
if [ -n "$ODOO20_SERVER" ] && _mig20_is_odoo20 "$ODOO20_SERVER"; then
    ok "Odoo 20 community at $ODOO20_SERVER"
    [ -f "$ODOO20_SERVER/odoo/cli/upgrade_code.py" ] && ok "upgrade_code tool present" || bad "odoo/cli/upgrade_code.py missing"
    git -C "$ODOO20_SERVER" status --porcelain >/dev/null 2>&1 \
        && ok "community checkout is a git repo (lets run_upgrade_code.sh prove core stays untouched)" \
        || warn "community is not a git checkout: the 'core untouched' safety check is skipped"
else
    bad "ODOO20_SERVER: no Odoo 20 checkout found. Set ODOO20_SERVER=/path/to/odoo (git clone -b 20.0 --depth 1 https://github.com/odoo/odoo)"
fi
if [ -n "$ODOO20_ENTERPRISE" ]; then ok "enterprise at $ODOO20_ENTERPRISE"
else warn "no enterprise addons: modules depending on enterprise apps cannot be installed/tested"; fi

# Python
if [ -n "$ODOO20_PYTHON" ]; then
    PYV=$("$ODOO20_PYTHON" -c 'import sys;print("%d.%d"%sys.version_info[:2])')
    ok "Python $PYV at $ODOO20_PYTHON"
    if [ -n "$ODOO20_SERVER" ] && [ -f "$ODOO20_SERVER/requirements.txt" ]; then
        MISSING=$("$ODOO20_PYTHON" - "$ODOO20_SERVER/requirements.txt" <<'PY'
import sys, re
from importlib import metadata
missing = []
for line in open(sys.argv[1]):
    line = line.split("#")[0].strip()
    if not line:
        continue
    req, _, marker = line.partition(";")
    name = re.split(r"[<>=!~ \[]", req.strip())[0]
    if marker.strip():
        try:
            try:
                from packaging.markers import Marker
            except ImportError:
                from pip._vendor.packaging.markers import Marker
            if not Marker(marker.strip()).evaluate():
                continue
        except Exception:
            pass
    try:
        metadata.version(name)
    except metadata.PackageNotFoundError:
        missing.append(name)
print(" ".join(missing))
PY
)
        [ -z "$MISSING" ] && ok "Odoo 20 requirements installed" || bad "missing Python packages: $MISSING  ->  $ODOO20_PYTHON -m pip install -r $ODOO20_SERVER/requirements.txt"
    fi
    "$ODOO20_PYTHON" -c "import websocket" 2>/dev/null && ok "websocket-client (browser smoke tests)" \
        || warn "websocket-client missing: browser smoke tests are SKIPPED by Odoo  ->  $ODOO20_PYTHON -m pip install websocket-client"
else
    bad "ODOO20_PYTHON: no Python >= 3.12 with Odoo 20 requirements found. Create a venv and pip install -r requirements.txt, then set ODOO20_PYTHON"
fi

# PostgreSQL
if command -v psql >/dev/null 2>&1; then
    SV=$(psql "${MIG20_PG_ARGS[@]}" -d postgres -Atc "show server_version_num" 2>&1)
    if [[ "$SV" =~ ^[0-9]+$ ]]; then
        [ "$SV" -ge 160000 ] && ok "PostgreSQL server $((SV/10000)) reachable" \
            || bad "PostgreSQL server is $((SV/10000)); Odoo 20 needs >= 16 (set MIG20_DB_HOST/PORT to a 16+ server)"
        CAN=$(psql "${MIG20_PG_ARGS[@]}" -d postgres -Atc "select rolcreatedb or rolsuper from pg_roles where rolname = current_user" 2>/dev/null)
        [ "$CAN" = "t" ] && ok "DB role can create databases" || bad "DB role cannot create databases (needs CREATEDB)"
    else
        bad "cannot connect to PostgreSQL: $(echo "$SV" | head -1)  (set MIG20_DB_HOST/PORT/USER/PASSWORD or ODOO20_CONF)"
    fi
    command -v dropdb >/dev/null 2>&1 || warn "dropdb not found: test databases will not be dropped automatically"
else
    bad "psql not found (PostgreSQL client tools are needed to check and drop test databases)"
fi

# Tools
command -v git >/dev/null 2>&1 && ok "git" || bad "git not found"
command -v rsync >/dev/null 2>&1 && ok "rsync" || bad "rsync not found"
BROWSER=""
for b in google-chrome google-chrome-stable chromium chromium-browser "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
    command -v "$b" >/dev/null 2>&1 && BROWSER=$b && break
done
[ -n "$BROWSER" ] && ok "Chrome/Chromium for smoke tests ($BROWSER)" || warn "Chrome/Chromium not found: browser smoke tests are SKIPPED"
command -v node >/dev/null 2>&1 && ok "node (optional JS syntax checks)" || warn "node not found (optional: 'node --check' of rewritten JS)"

# Target
mkdir -p "$MIG20_TARGET_ROOT" 2>/dev/null && [ -w "$MIG20_TARGET_ROOT" ] && ok "target root writable: $MIG20_TARGET_ROOT" \
    || bad "cannot write MIG20_TARGET_ROOT=$MIG20_TARGET_ROOT"

# Odoo's own skills (optional, used for house style and the review step)
FOUND=""
for d in "$(dirname "$_MIG20_SKILL_DIR")" "$HOME/.agents/skills" "$HOME/.claude/skills" "${CODEX_HOME:-$HOME/.codex}/skills" "$HOME/.copilot/skills"; do
    [ -f "$d/odoo-review/SKILL.md" ] && FOUND="$d" && break
done
if [ -n "$FOUND" ]; then ok "odoo-review skill installed ($FOUND)"
elif [ -f "$ODOO20_SERVER/skills/odoo-review/SKILL.md" ]; then ok "odoo-review available in $ODOO20_SERVER/skills (read from there; install as skills with: cp -r $ODOO20_SERVER/skills/* ~/.agents/skills/)"
else warn "odoo-review skill not available (review step will use general judgement)"; fi

if [ $WRITE = 1 ]; then
    CFG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/odoo-migrate-to-20"
    mkdir -p "$CFG_DIR"
    {
        echo "# written by doctor.sh $(date -u +%Y-%m-%dT%H:%M:%SZ); edit freely"
        for v in ODOO20_SERVER ODOO20_ENTERPRISE ODOO20_PYTHON ODOO20_CONF MIG20_DB_HOST MIG20_DB_PORT MIG20_DB_USER MIG20_DB_PASSWORD MIG20_TARGET_ROOT MIG20_HTTP_PORT MIG20_DATA_DIR MIG20_OLD_SOURCES; do
            echo "$v=${!v:-}"
        done
    } > "$CFG_DIR/config.env"
    chmod 600 "$CFG_DIR/config.env"
    echo; echo "Saved $CFG_DIR/config.env"
fi
echo
[ $FAIL = 0 ] && echo "READY" || echo "NOT READY: fix the FAIL lines above"
exit $FAIL
