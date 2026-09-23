#!/bin/bash
# Copy a source module into the Odoo 20 custom addons tree and commit a baseline,
# so every migration change is a reviewable git diff. The source is never modified.
#
#   prepare.sh <source_module_dir> <project> [<from_version>]
#
# Prints: DEST=<path> FROM=<version> BASELINE=<commit>
set -euo pipefail
source "$(dirname "$0")/env.sh"

SRC=$(realpath "${1:?source module dir}")
PROJECT=${2:?project name}
ROOT=$MIG20_TARGET_ROOT
MODULE=$(basename "$SRC")
PROJ_DIR="$ROOT/$PROJECT"
DEST="$PROJ_DIR/$MODULE"

[ -f "$SRC/__manifest__.py" ] || { echo "ERROR: $SRC has no __manifest__.py" >&2; exit 2; }
[ -e "$DEST" ] && { echo "ERROR: $DEST already exists (migrated before?). Remove it or pick another project." >&2; exit 2; }

# Source version: explicit arg, else the manifest version prefix (14.0.x.y.z), else a version in the path.
FROM=${3:-}
if [ -z "$FROM" ]; then
    FROM=$(python3 -c "import ast,sys;v=str(ast.literal_eval(open(sys.argv[1]).read()).get('version',''));p=v.split('.');print(p[0]+'.0' if len(p)>=4 and p[0].isdigit() and 8<=int(p[0])<=19 else '')" "$SRC/__manifest__.py")
fi
if [ -z "$FROM" ]; then  # e.g. /x/odoo16_custom/..., /x/odoo-17/..., /x/16.0/..., /x/v15/...
    FROM=$(echo "$SRC" | grep -oE '(odoo[_-]?|v|/)(1[0-9])([._-]0)?([_/-]|$)' | grep -oE '1[0-9]' | head -1 || true)
    [ -n "$FROM" ] && FROM="$FROM.0"
fi
[ -n "$FROM" ] || { echo "ERROR: cannot detect the source Odoo version; pass it as 3rd argument (e.g. 16.0)" >&2; exit 2; }

mkdir -p "$PROJ_DIR/.migration"
rsync -a --exclude .git --exclude __pycache__ --exclude '*.pyc' --exclude node_modules "$SRC/" "$DEST/"

# Fingerprint of the source, to prove at the end that it was not touched.
mig20_sha1_tree "$SRC" > "$PROJ_DIR/.migration/$MODULE.source.sha1"
echo "$SRC" > "$PROJ_DIR/.migration/$MODULE.source.path"
echo "$FROM" > "$PROJ_DIR/.migration/$MODULE.from"

cd "$PROJ_DIR"
[ -d .git ] || git init -q
cat > .gitignore <<'EOF'
__pycache__/
*.pyc
.migration/*.log
.migration/screenshots/
EOF
git add .gitignore "$MODULE" .migration
git commit -q -m "[MIG] $MODULE: baseline copy from Odoo $FROM ($SRC)"
echo "DEST=$DEST"
echo "FROM=$FROM"
echo "BASELINE=$(git rev-parse --short HEAD)"
