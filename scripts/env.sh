#!/bin/bash
# Shared configuration for the odoo-migrate-to-20 scripts. Source it; do not execute it.
#
# Every value can be set in the environment or in a config file; the first found wins:
#   $MIG20_CONFIG
#   ${XDG_CONFIG_HOME:-~/.config}/odoo-migrate-to-20/config.env
#   <skill dir>/config.env
# Unset values are auto-detected. Run scripts/doctor.sh to see and save the result.
#
#   ODOO20_SERVER      Odoo 20 community checkout (contains odoo-bin)            required
#   ODOO20_ENTERPRISE  Odoo 20 enterprise addons dir                              optional
#   ODOO20_PYTHON      Python >= 3.12 with Odoo 20 requirements installed         required
#   ODOO20_CONF        an odoo.conf to start from (db credentials etc.)           optional
#   MIG20_DB_HOST / MIG20_DB_PORT / MIG20_DB_USER / MIG20_DB_PASSWORD
#                      PostgreSQL >= 16 used for throwaway test databases         optional (read from ODOO20_CONF, else libpq defaults)
#   MIG20_TARGET_ROOT  where migrated modules go: <root>/<project>/<module>        default: <parent of ODOO20_SERVER>/odoo20_custom_addons
#   MIG20_HTTP_PORT    port for test servers                                       default: 8121
#   MIG20_DATA_DIR     Odoo data dir (filestore) for test databases                default: ~/.local/share/Odoo
#   MIG20_OLD_SOURCES  optional colon-separated Odoo checkouts of older versions, used to look up what an API used to be

_MIG20_SKILL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

for _f in "${MIG20_CONFIG:-}" "${XDG_CONFIG_HOME:-$HOME/.config}/odoo-migrate-to-20/config.env" "$HOME/.config/odoo-migrate-to-20/config.env" "$_MIG20_SKILL_DIR/config.env"; do
    if [ -n "$_f" ] && [ -f "$_f" ]; then
        # only KEY=VALUE lines; values already in the environment win
        while IFS='=' read -r _k _v; do
            case "$_k" in ''|\#*) continue;; esac
            _v=${_v%\"}; _v=${_v#\"}; _v=${_v%\'}; _v=${_v#\'}
            [ -z "${!_k:-}" ] && export "$_k=$_v"
        done < "$_f"
        MIG20_CONFIG_FILE=$_f
        break
    fi
done

_mig20_is_odoo20() {  # <dir> -> true if it is an Odoo 20 community checkout
    [ -f "$1/odoo-bin" ] && [ -f "$1/odoo/release.py" ] &&
        grep -qE "^version_info = \(20," "$1/odoo/release.py"
}

if [ -z "${ODOO20_SERVER:-}" ]; then
    for _c in "$PWD" "$HOME/odoo20" "$HOME/odoo/20.0" "$HOME/src/odoo" "$HOME/odoo" /odoo/odoo20-server /opt/odoo20 /opt/odoo/odoo20 /opt/odoo20/odoo /srv/odoo20 \
              $(ls -d "$HOME"/*/odoo*20* /odoo/*20* /opt/*/*20* 2>/dev/null); do
        if _mig20_is_odoo20 "$_c"; then ODOO20_SERVER=$(cd "$_c" && pwd); break; fi
    done
fi
export ODOO20_SERVER=${ODOO20_SERVER:-}

if [ -z "${ODOO20_ENTERPRISE:-}" ] && [ -n "$ODOO20_SERVER" ]; then
    _p=$(dirname "$ODOO20_SERVER")
    for _c in "$_p/enterprise" "$_p/odoo_enterprise_20" "$_p/enterprise-20.0" "$_p/enterprise20" $(ls -d "$_p"/*enterprise*20* 2>/dev/null); do
        [ -f "$_c/web_enterprise/__manifest__.py" ] || continue
        # a git checkout must be on a 20.x branch; a plain folder is accepted
        _b=$(git -C "$_c" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
        if [ -z "$_b" ] || [[ "$_b" == *20* ]]; then ODOO20_ENTERPRISE=$(cd "$_c" && pwd); break; fi
    done
fi
export ODOO20_ENTERPRISE=${ODOO20_ENTERPRISE:-}

if [ -z "${ODOO20_PYTHON:-}" ]; then
    for _c in "${VIRTUAL_ENV:+$VIRTUAL_ENV/bin/python}" "$ODOO20_SERVER/venv/bin/python" "$ODOO20_SERVER/.venv/bin/python" \
              $(ls -d /opt/odoo/odoo20*/bin/python "$HOME"/.venvs/odoo20*/bin/python "$HOME"/venvs/odoo20*/bin/python 2>/dev/null) python3.14 python3.13 python3.12 python3; do
        [ -z "$_c" ] && continue
        if command -v "$_c" >/dev/null 2>&1 && "$_c" -c "import sys, psycopg2, lxml, werkzeug; sys.exit(sys.version_info < (3, 12))" 2>/dev/null; then
            ODOO20_PYTHON=$(command -v "$_c"); break
        fi
    done
fi
export ODOO20_PYTHON=${ODOO20_PYTHON:-}

# DB settings: explicit > from ODOO20_CONF > libpq defaults
_mig20_conf_get() {  # <key> -> value from ODOO20_CONF, '' if False/absent
    [ -n "${ODOO20_CONF:-}" ] && [ -f "$ODOO20_CONF" ] || return 0
    sed -nE "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*(.*)[[:space:]]*$/\1/p" "$ODOO20_CONF" | tail -1 | grep -v '^False$' || true
}
export MIG20_DB_HOST=${MIG20_DB_HOST:-$(_mig20_conf_get db_host)}
export MIG20_DB_PORT=${MIG20_DB_PORT:-$(_mig20_conf_get db_port)}
export MIG20_DB_USER=${MIG20_DB_USER:-$(_mig20_conf_get db_user)}
export MIG20_DB_PASSWORD=${MIG20_DB_PASSWORD:-$(_mig20_conf_get db_password)}

if [ -z "${MIG20_TARGET_ROOT:-}" ] && [ -n "$ODOO20_SERVER" ]; then
    MIG20_TARGET_ROOT="$(dirname "$ODOO20_SERVER")/odoo20_custom_addons"
fi
export MIG20_TARGET_ROOT=${MIG20_TARGET_ROOT:-$HOME/odoo20_custom_addons}
export MIG20_HTTP_PORT=${MIG20_HTTP_PORT:-8121}
export MIG20_DATA_DIR=${MIG20_DATA_DIR:-$HOME/.local/share/Odoo}
export MIG20_OLD_SOURCES=${MIG20_OLD_SOURCES:-}

# Core addons path (community, then enterprise when present)
MIG20_CORE_ADDONS="$ODOO20_SERVER/addons,$ODOO20_SERVER/odoo/addons${ODOO20_ENTERPRISE:+,$ODOO20_ENTERPRISE}"
export MIG20_CORE_ADDONS

# psql/createdb/dropdb connection flags (libpq)
MIG20_PG_ARGS=()
[ -n "$MIG20_DB_HOST" ] && MIG20_PG_ARGS+=(-h "$MIG20_DB_HOST")
[ -n "$MIG20_DB_PORT" ] && MIG20_PG_ARGS+=(-p "$MIG20_DB_PORT")
[ -n "$MIG20_DB_USER" ] && MIG20_PG_ARGS+=(-U "$MIG20_DB_USER")
[ -n "$MIG20_DB_PASSWORD" ] && export PGPASSWORD="$MIG20_DB_PASSWORD"

# odoo-bin connection flags
MIG20_ODOO_DB_ARGS=()
[ -n "${ODOO20_CONF:-}" ] && [ -f "$ODOO20_CONF" ] && MIG20_ODOO_DB_ARGS+=(-c "$ODOO20_CONF")
[ -n "$MIG20_DB_HOST" ] && MIG20_ODOO_DB_ARGS+=(--db_host "$MIG20_DB_HOST")
[ -n "$MIG20_DB_PORT" ] && MIG20_ODOO_DB_ARGS+=(--db_port "$MIG20_DB_PORT")
[ -n "$MIG20_DB_USER" ] && MIG20_ODOO_DB_ARGS+=(-r "$MIG20_DB_USER")
[ -n "$MIG20_DB_PASSWORD" ] && MIG20_ODOO_DB_ARGS+=(-w "$MIG20_DB_PASSWORD")

mig20_require() {  # abort with a helpful message when the essentials are missing
    local ok=1
    [ -n "$ODOO20_SERVER" ] && _mig20_is_odoo20 "$ODOO20_SERVER" || { echo "ERROR: ODOO20_SERVER not set or not an Odoo 20 checkout ('$ODOO20_SERVER'). Run scripts/doctor.sh." >&2; ok=0; }
    [ -n "$ODOO20_PYTHON" ] || { echo "ERROR: ODOO20_PYTHON not found (Python >= 3.12 with Odoo 20 requirements). Run scripts/doctor.sh." >&2; ok=0; }
    [ $ok = 1 ] || exit 2
}

mig20_sha1_tree() {  # <dir> -> sorted "sha1  path" list (portable: no sha1sum on macOS)
    python3 - "$1" <<'PY'
import hashlib, os, sys
root = sys.argv[1]
for dp, dn, fn in os.walk(root):
    dn[:] = sorted(d for d in dn if d not in ("__pycache__", ".git", "node_modules"))
    for f in sorted(fn):
        if f.endswith(".pyc"):
            continue
        p = os.path.join(dp, f)
        print(hashlib.sha1(open(p, "rb").read()).hexdigest() + "  " + os.path.relpath(p, root))
PY
}
