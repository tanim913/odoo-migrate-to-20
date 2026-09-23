#!/bin/bash
# Install the odoo-migrate-to-20 skill for one or more coding agents.
#
#   ./install.sh [--for LIST] [--project DIR] [--dest DIR] [--link] [--uninstall] [--dry-run]
#
#   --for LIST     comma-separated targets (default: agents,claude):
#                    agents       ~/.agents/skills/            open Agent Skills location (Codex, Gemini CLI, OpenCode, Copilot CLI, Cursor, ...)
#                    claude       ~/.claude/skills/            Claude Code
#                    codex        ~/.codex/skills/             OpenAI Codex
#                    cursor       .cursor/rules/*.mdc + .cursor/commands/*.md          (user level, or --project)
#                    antigravity  .antigravity/skills/*.md + .agent/workflows/*.md     (needs --project)
#                    copilot      .github/prompts/*.prompt.md + ~/.copilot/skills/     (prompt needs --project)
#                    gemini       .gemini/commands/*.toml                              (user level, or --project)
#                    agents-md    AGENTS.md section, read by most agents               (needs --project)
#                    all          every target above
#   --project DIR  also install project-level adapters into DIR (the repo you open in the IDE)
#   --project-skills  with --project: also link the skill into DIR/.agents/skills and DIR/.claude/skills
#                  (only for a repo shared with a team; otherwise the user-level copy is enough and
#                  a second copy would make some tools list the skill twice)
#   --dest DIR     where the canonical copy lives (default: ~/.agents/skills/odoo-migrate-to-20)
#   --link         symlink the canonical copy to this folder instead of copying (for skill developers)
#   --uninstall    remove what this script installs for the chosen targets
#   --dry-run      print what would be done
#
# Skill-aware agents get the whole skill folder (SKILL.md + scripts + references). Agents that only
# know rules/commands get a small adapter that tells the model to read the canonical SKILL.md and
# follow it, so there is a single source of truth.
set -euo pipefail

NAME=odoo-migrate-to-20
SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FOR="agents,claude"; PROJECT=""; PROJECT_SKILLS=0; DEST="$HOME/.agents/skills/$NAME"; LINK=0; UNINSTALL=0; DRY=0
while [ $# -gt 0 ]; do
    case "$1" in
        --for) FOR=$2; shift;;
        --project) PROJECT=$(cd "$2" && pwd); shift;;
        --project-skills) PROJECT_SKILLS=1;;
        --dest) DEST=$2; shift;;
        --link) LINK=1;;
        --uninstall) UNINSTALL=1;;
        --dry-run) DRY=1;;
        -h|--help) sed -n '2,30p' "$0"; exit 0;;
        *) echo "unknown option $1" >&2; exit 2;;
    esac
    shift
done
[ "$FOR" = all ] && FOR="agents,claude,codex,cursor,antigravity,copilot,gemini,agents-md"

run() { if [ $DRY = 1 ]; then echo "  would: $*"; else "$@"; fi; }
say() { echo "$*"; }
write() {  # write <file> (content on stdin)
    local f=$1
    if [ $DRY = 1 ]; then echo "  would write $f"; cat >/dev/null; return; fi
    mkdir -p "$(dirname "$f")"; cat > "$f"; echo "  wrote $f"
}
remove() { if [ -e "$1" ] || [ -L "$1" ]; then run rm -rf "$1"; echo "  removed $1"; fi; }

TRIGGER="migrate, port or upgrade an Odoo module (or addons folder) from Odoo 14, 15, 16, 17, 18 or 19 to Odoo 20, or make a module installable on Odoo 20"
DESCRIPTION="Migrate custom Odoo modules from Odoo 14-19 to Odoo 20 and prove they install and run: safe upgrade_code pass, breaking-change scanner, per-area rewrites (Python/ORM, views, security, Owl 3 JS, website Interactions), install + browser smoke tests on a throwaway DB, review and report. Use when asked to $TRIGGER."

adapter_body() {  # the instructions every adapter carries; $1 = canonical skill dir
cat <<EOF
# Odoo → 20 migration (odoo-migrate-to-20)

When the user asks to $TRIGGER:

1. Read \`$1/SKILL.md\` **completely** and follow its workflow exactly. It is the single source of truth.
2. Scripts are in \`$1/scripts/\`, knowledge in \`$1/references/\`. Open the reference files the
   workflow names, by path, before editing the matching code.
3. Start with \`$1/scripts/doctor.sh\` and do not migrate until it prints READY (or the user accepts
   what is missing).
4. Never edit the source module or the Odoo 20 source tree; work only on the copy that
   \`scripts/prepare.sh\` creates.

User request: {{REQUEST}}
EOF
}

# ---------------------------------------------------------------- canonical copy
canonical() {
    if [ $UNINSTALL = 1 ]; then remove "$DEST"; return; fi
    if [ "$(cd "$SRC" && pwd -P)" = "$( [ -d "$DEST" ] && cd "$DEST" && pwd -P || echo none)" ]; then
        say "canonical copy: $DEST (this folder)"; return
    fi
    say "canonical copy -> $DEST"
    run mkdir -p "$(dirname "$DEST")"
    [ -e "$DEST" ] || [ -L "$DEST" ] && run rm -rf "$DEST"
    if [ $LINK = 1 ]; then run ln -s "$SRC" "$DEST"
    else run rsync -a --exclude .git --exclude __pycache__ --exclude config.env "$SRC/" "$DEST/"; fi
    run chmod +x "$DEST"/scripts/*.sh "$DEST"/scripts/*.py "$DEST"/install.sh 2>/dev/null || true
}

skill_dir_link() {  # skill_dir_link <skills_root>: expose the canonical folder in another agent's skills dir
    local target="$1/$NAME"
    if [ $UNINSTALL = 1 ]; then remove "$target"; return; fi
    if [ "$(cd "$1" 2>/dev/null && pwd -P)/$NAME" = "$(cd "$DEST" && pwd -P)" ]; then return; fi
    if [ -d "$target" ] && [ ! -L "$target" ] && [ "$(cd "$target" && pwd -P)" = "$(cd "$SRC" && pwd -P)" ]; then
        say "  $target is this source folder: left as is"; return
    fi
    run mkdir -p "$1"; [ -e "$target" ] || [ -L "$target" ] && run rm -rf "$target"
    run ln -s "$DEST" "$target"; echo "  linked $target -> $DEST"
}

need_project() { [ -n "$PROJECT" ] || { say "  skipped: pass --project <repo dir> for $1"; return 1; }; }

# ---------------------------------------------------------------- targets
t_agents()  { say "[agents] open Agent Skills location"; { [ -n "$PROJECT" ] && [ $PROJECT_SKILLS = 1 ]; } && skill_dir_link "$PROJECT/.agents/skills"; true; }
t_claude()  { say "[claude] Claude Code"; skill_dir_link "$HOME/.claude/skills"; { [ -n "$PROJECT" ] && [ $PROJECT_SKILLS = 1 ]; } && skill_dir_link "$PROJECT/.claude/skills"; true; }
t_codex()   { say "[codex] OpenAI Codex"; skill_dir_link "${CODEX_HOME:-$HOME/.codex}/skills"; }

t_cursor() {
    say "[cursor] Cursor rule + slash command"
    local roots=("$HOME/.cursor"); [ -n "$PROJECT" ] && roots+=("$PROJECT/.cursor")
    for r in "${roots[@]}"; do
        if [ $UNINSTALL = 1 ]; then remove "$r/rules/$NAME.mdc"; remove "$r/commands/$NAME.md"; continue; fi
        { printf -- '---\ndescription: "%s"\nglobs: []\nalwaysApply: false\n---\n\n' "$DESCRIPTION"
          adapter_body "$DEST" | sed 's/{{REQUEST}}/(see the conversation)/'; } | write "$r/rules/$NAME.mdc"
        adapter_body "$DEST" | sed 's/{{REQUEST}}/$ARGUMENTS/' | write "$r/commands/$NAME.md"
    done
}

t_antigravity() {
    say "[antigravity] Antigravity skill + workflow"
    need_project antigravity || return 0
    if [ $UNINSTALL = 1 ]; then remove "$PROJECT/.antigravity/skills/$NAME.md"; remove "$PROJECT/.agent/workflows/$NAME.md"; return; fi
    { printf -- '---\nname: %s\ndescription: |\n  %s\n---\n\n' "$NAME" "$DESCRIPTION"
      adapter_body "$DEST" | sed 's/{{REQUEST}}/(see the conversation)/'; } | write "$PROJECT/.antigravity/skills/$NAME.md"
    { printf -- '---\ndescription: %s\n---\n\n' "Migrate an Odoo 14-19 module to Odoo 20 (odoo-migrate-to-20)"
      adapter_body "$DEST" | sed 's/{{REQUEST}}/the module path given after the command/'; } | write "$PROJECT/.agent/workflows/$NAME.md"
}

t_copilot() {
    say "[copilot] GitHub Copilot"
    skill_dir_link "$HOME/.copilot/skills"
    need_project "copilot prompt file" || return 0
    if [ $UNINSTALL = 1 ]; then remove "$PROJECT/.github/prompts/$NAME.prompt.md"; return; fi
    { printf -- '---\nmode: agent\ndescription: %s\n---\n\n' "Migrate an Odoo 14-19 module to Odoo 20"
      adapter_body "$DEST" | sed 's/{{REQUEST}}/${input:module:Path of the module to migrate}/'; } | write "$PROJECT/.github/prompts/$NAME.prompt.md"
}

t_gemini() {
    say "[gemini] Gemini CLI custom command"
    local roots=("$HOME/.gemini"); [ -n "$PROJECT" ] && roots+=("$PROJECT/.gemini")
    for r in "${roots[@]}"; do
        if [ $UNINSTALL = 1 ]; then remove "$r/commands/$NAME.toml"; continue; fi
        { printf 'description = "Migrate an Odoo 14-19 module to Odoo 20"\nprompt = """\n'
          adapter_body "$DEST" | sed 's/{{REQUEST}}/{{args}}/'
          printf '"""\n'; } | write "$r/commands/$NAME.toml"
    done
}

t_agents_md() {
    say "[agents-md] AGENTS.md section"
    need_project AGENTS.md || return 0
    local f="$PROJECT/AGENTS.md" begin="<!-- BEGIN $NAME -->" end="<!-- END $NAME -->"
    local tmp; tmp=$(mktemp)
    [ -f "$f" ] && awk -v b="$begin" -v e="$end" '$0==b{skip=1} !skip{print} $0==e{skip=0}' "$f" > "$tmp" || : > "$tmp"
    if [ $UNINSTALL = 0 ]; then
        { echo "$begin"; adapter_body "$DEST" | sed 's/{{REQUEST}}/(see the conversation)/'; echo "$end"; } >> "$tmp"
    fi
    if [ $DRY = 1 ]; then echo "  would update $f"; else mv "$tmp" "$f"; echo "  updated $f"; fi
}

canonical
IFS=',' read -ra TARGETS <<< "$FOR"
for t in "${TARGETS[@]}"; do
    case "$t" in
        agents) t_agents;; claude) t_claude;; codex) t_codex;; cursor) t_cursor;;
        antigravity) t_antigravity;; copilot) t_copilot;; gemini) t_gemini;; agents-md) t_agents_md;;
        *) echo "unknown target: $t" >&2; exit 2;;
    esac
done
[ $UNINSTALL = 1 ] && { say "uninstalled"; exit 0; }
say
say "Next: $DEST/scripts/doctor.sh   (checks Odoo 20, Python, PostgreSQL; add --write to save the config)"
