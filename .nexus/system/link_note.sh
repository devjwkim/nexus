#!/usr/bin/env bash
set -euo pipefail

# link_note.sh
# - MODE=init    : Move project note to Google Drive and create link (new connection)
# - MODE=connect : Connect existing Google Drive note to project via link only (import existing)

say() { printf "%s\n" "$*"; }
die() { printf "❌ %s\n" "$*" >&2; exit 1; }

is_symlink() { [ -L "$1" ]; }
exists() { [ -e "$1" ]; }

backup_path() {
  local p="$1"
  local ts
  ts="$(date +%Y%m%d%H%M%S)"
  echo "${p}_backup_${ts}"
}

ensure_parent_dir() {
  local p="$1"
  local parent
  parent="$(dirname "$p")"
  mkdir -p "$parent"
}

read_input() {
  local prompt="$1"
  local varname="$2"
  local default="${3:-}"
  local val=""
  if [ -n "$default" ]; then
    read -r -p "${prompt} [default: ${default}]: " val
    val="${val:-$default}"
  else
    read -r -p "${prompt}: " val
  fi
  [ -n "$val" ] || die "Input is empty: $prompt"
  printf -v "$varname" "%s" "$val"
}

confirm_yesno() {
  local prompt="$1"
  local default="${2:-N}"  # Y/N
  local ans=""
  read -r -p "${prompt} (Y/N) [default: ${default}]: " ans
  ans="${ans:-$default}"
  case "$ans" in
    Y|y) return 0 ;;
    N|n) return 1 ;;
    *) die "Please enter Y or N only." ;;
  esac
}

make_link() {
  local target="$1"
  local linkpath="$2"
  ensure_parent_dir "$linkpath"

  # Handle if linkpath exists
  if exists "$linkpath"; then
    die "Link location already exists: $linkpath (cleanup required first)"
  fi

  ln -s "$target" "$linkpath"
}

replace_link_force() {
  local target="$1"
  local linkpath="$2"
  ensure_parent_dir "$linkpath"

  if exists "$linkpath" || is_symlink "$linkpath"; then
    rm -rf "$linkpath"
  fi
  ln -s "$target" "$linkpath"
}

main() {
  say "=============================="
  say "🔗 Nexus note symbolic link tool"
  say "=============================="

  local MODE=""
  read_input "Select MODE (init=new connection / connect=import existing)" MODE "connect"
  case "$MODE" in
    init|connect) ;;
    *) die "MODE must be either init or connect." ;;
  esac

  local GD_NOTE=""
  local PRJ_NOTE=""

  read_input "Google Drive note path" GD_NOTE
  read_input "Project note path" PRJ_NOTE

  # Path normalization: use as-is since may contain slashes/spaces
  say ""
  say "MODE      : $MODE"
  say "GD_NOTE   : $GD_NOTE"
  say "PRJ_NOTE  : $PRJ_NOTE"
  say ""

  # Common checks
  ensure_parent_dir "$GD_NOTE"
  ensure_parent_dir "$PRJ_NOTE"

  if [ "$MODE" = "init" ]; then
    # 1) Project note must exist to move (or create if missing)
    if ! exists "$PRJ_NOTE"; then
      say "⚠️ Project note does not exist. Creating empty note folder: $PRJ_NOTE"
      mkdir -p "$PRJ_NOTE"
    fi

    # 2) If GD_NOTE already exists, decide whether to overwrite
    if exists "$GD_NOTE"; then
      say "⚠️ Google Drive note path already exists: $GD_NOTE"
      if confirm_yesno "Overwrite (delete) Google Drive note and move new one?" "N"; then
        rm -rf "$GD_NOTE"
      else
        die "Aborted: Keeping existing Google Drive note. Use MODE=connect instead."
      fi
    fi

    # 3) Move project note to Google Drive
    say "➡️ Moving: $PRJ_NOTE -> $GD_NOTE"
    mv "$PRJ_NOTE" "$GD_NOTE"

    # 4) Create symbolic link at project location
    say "➡️ Creating link: $PRJ_NOTE -> $GD_NOTE"
    make_link "$GD_NOTE" "$PRJ_NOTE"

    say "✅ Complete (init): Moved project note to Drive and linked."

  else
    # MODE=connect
    # 1) GD_NOTE must exist
    if ! exists "$GD_NOTE"; then
      die "Google Drive note path does not exist (check sync/path): $GD_NOTE"
    fi

    # 2) Handle project note
    if exists "$PRJ_NOTE" || is_symlink "$PRJ_NOTE"; then
      if is_symlink "$PRJ_NOTE"; then
        local cur_target
        cur_target="$(readlink "$PRJ_NOTE" || true)"
        say "ℹ️ Project note is already a symbolic link: $PRJ_NOTE -> $cur_target"
        if [ "$cur_target" = "$GD_NOTE" ]; then
          say "✅ Already linked to desired target. (No changes)"
          exit 0
        fi
        if confirm_yesno "Remove existing link and reconnect to new target?" "Y"; then
          replace_link_force "$GD_NOTE" "$PRJ_NOTE"
          say "✅ Complete (connect): Replaced link with new target."
          exit 0
        else
          die "Aborted: Keeping existing link"
        fi
      else
        # Actual folder/file exists
        say "⚠️ Actual folder/file exists at project note path: $PRJ_NOTE"
        if confirm_yesno "Backup existing note and replace with link?" "Y"; then
          local bk
          bk="$(backup_path "$PRJ_NOTE")"
          say "➡️ Backup: $PRJ_NOTE -> $bk"
          mv "$PRJ_NOTE" "$bk"
        else
          if confirm_yesno "Delete without backup and replace with link? (DANGEROUS)" "N"; then
            rm -rf "$PRJ_NOTE"
          else
            die "Aborted: Keeping existing note."
          fi
        fi
      fi
    fi

    # 3) Create link
    say "➡️ Creating link: $PRJ_NOTE -> $GD_NOTE"
    make_link "$GD_NOTE" "$PRJ_NOTE"

    say "✅ Complete (connect): Linked project note to Google Drive note."
  fi
}

main "$@"
