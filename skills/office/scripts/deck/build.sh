#!/bin/bash
set -e
SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SRC="${SRC:-slides.html}"
NAME="${NAME:-$(basename "$(pwd)")}"
FORMATS="${FORMATS:-html,review}"
BUILD_DIR="${BUILD_DIR:-build}"
WORK_DIR="$(pwd -P)"
SOURCE_PATH="$SRC"
BUILD_PATH="$BUILD_DIR"
case "$SOURCE_PATH" in
  /*) ;;
  *) SOURCE_PATH="${WORK_DIR}/${SOURCE_PATH}" ;;
esac
case "$BUILD_PATH" in
  /*) ;;
  *) BUILD_PATH="${WORK_DIR}/${BUILD_PATH}" ;;
esac

if [ ! -f "$SRC" ]; then
  echo "Working directory: $(pwd)" >&2
  echo "SRC: $SRC" >&2
  echo "Directory entries:" >&2
  ls -la . 2>&1 | sed -n '1,5p' >&2
  echo "Error: $SRC not found. Create slides.html or set SRC=yourfile.html" >&2
  exit 1
fi

if [ ! -f DESIGN.md ]; then
  echo "[warning] DESIGN.md missing; build continues, but visual review may mark weak design identity." >&2
fi

if [ ! -f deck-brief.md ]; then
  echo "[warning] deck-brief.md missing; build continues without slide-count cross-check." >&2
fi

if [ ! -f required-visible-text.txt ]; then
  echo "[warning] required-visible-text.txt missing; manually verify required source facts before delivery." >&2
fi

case "$SOURCE_PATH" in
  *.html) ;;
  *) echo "Error: presentation now uses HTML-first source only. Create slides.html or set SRC=yourfile.html." >&2; exit 1 ;;
esac

python3 - "$SOURCE_PATH" <<'PY'
import pathlib
import re
import sys

source_path = pathlib.Path(sys.argv[1])
deck_brief_path = pathlib.Path("deck-brief.md")
text = source_path.read_text()
deck_brief_text = deck_brief_path.read_text() if deck_brief_path.exists() else ""
if "design-source: DESIGN.md" not in text:
    print(f"Warning: {source_path.name} should include design-source: DESIGN.md", file=sys.stderr)

if "<section" not in text.lower():
    print("Error: slides.html must contain slide <section> elements.")
    sys.exit(1)

def extract_requested_slide_count(deck_brief_text):
    for pattern in [
        r"(?im)^\s*slide\s*count\s*[:：-]\s*(\d{1,2})\b",
        r"(?im)^\s*slides?\s*[:：-]\s*(\d{1,2})\b",
        r"(?im)^\s*슬라이드\s*수\s*[:：-]\s*(\d{1,2})\b",
    ]:
        match = re.search(pattern, deck_brief_text)
        if match:
            return int(match.group(1))
    numbered_slide_items = re.findall(r"(?m)^\s*\d{1,2}\.\s+\S", deck_brief_text)
    if len(numbered_slide_items) >= 2:
        return len(numbered_slide_items)
    return None

requested_slide_count = extract_requested_slide_count(deck_brief_text) if deck_brief_text else None
actual_slide_count = len(re.findall(r"<section\b", text, re.IGNORECASE))
if requested_slide_count is not None and actual_slide_count != requested_slide_count:
    print(
        f"Warning: slides.html has {actual_slide_count} slide sections, but deck-brief.md says {requested_slide_count}. "
        "If the user asked for an exact count, fix slides.html; otherwise update deck-brief.md.",
        file=sys.stderr,
    )
PY

SKILL_ASSET_DIRECTORY="${SKILL_ASSET_DIRECTORY:-${SCRIPT_DIRECTORY}/../../assets}"
if [ ! -f "${SKILL_ASSET_DIRECTORY}/package.json" ] && [ -f "${SCRIPT_DIRECTORY}/package.json" ]; then
  SKILL_ASSET_DIRECTORY="$SCRIPT_DIRECTORY"
fi
if [ ! -f "${SKILL_ASSET_DIRECTORY}/package.json" ] && [ -f "${SCRIPT_DIRECTORY}/../../assets/package.json" ]; then
  SKILL_ASSET_DIRECTORY="${SCRIPT_DIRECTORY}/../../assets"
fi
RENDER_REVIEW_SCRIPT="${RENDER_REVIEW_SCRIPT:-${SCRIPT_DIRECTORY}/render_review.py}"
HTML_EXPORT_SCRIPT="${HTML_EXPORT_SCRIPT:-${SCRIPT_DIRECTORY}/html_export.py}"
HTML_RENDER_SCRIPT="${HTML_RENDER_SCRIPT:-${SCRIPT_DIRECTORY}/html_render.mjs}"
if [ ! -f "$RENDER_REVIEW_SCRIPT" ] && [ -f "${SCRIPT_DIRECTORY}/../scripts/render_review.py" ]; then
  RENDER_REVIEW_SCRIPT="${SCRIPT_DIRECTORY}/../scripts/render_review.py"
fi
if [ ! -f "$HTML_EXPORT_SCRIPT" ] && [ -f "${SCRIPT_DIRECTORY}/../scripts/html_export.py" ]; then
  HTML_EXPORT_SCRIPT="${SCRIPT_DIRECTORY}/../scripts/html_export.py"
fi
if [ ! -f "$HTML_RENDER_SCRIPT" ] && [ -f "${SCRIPT_DIRECTORY}/../scripts/html_render.mjs" ]; then
  HTML_RENDER_SCRIPT="${SCRIPT_DIRECTORY}/../scripts/html_render.mjs"
fi
NODE_RUNTIME_ROOT="${WORK_DIR}/.skill-env/presentation/node"
NODE_RUNTIME_TMP="${WORK_DIR}/.skill-env/presentation/tmp"
NODE_RUNTIME_BUN_INSTALL="${WORK_DIR}/.skill-env/presentation/bun-install"
NODE_RUNTIME_BUN_CACHE="${WORK_DIR}/.skill-env/presentation/bun-cache"

ensure_node_environment() {
  if ! command -v bun &> /dev/null; then
    echo "bun is required for script-managed HTML-first slide export."
    return 1
  fi
  if [ ! -f "${SKILL_ASSET_DIRECTORY}/package.json" ]; then
    echo "Slide export package manifest is missing: ${SKILL_ASSET_DIRECTORY}/package.json"
    return 1
  fi
  mkdir -p "$NODE_RUNTIME_ROOT" "$NODE_RUNTIME_TMP" "$NODE_RUNTIME_BUN_INSTALL" "$NODE_RUNTIME_BUN_CACHE"
  export BUN_INSTALL="$NODE_RUNTIME_BUN_INSTALL"
  export BUN_TMPDIR="$NODE_RUNTIME_TMP"
  export BUN_INSTALL_CACHE_DIR="$NODE_RUNTIME_BUN_CACHE"
  export TMPDIR="$NODE_RUNTIME_TMP"
  export TMP="$NODE_RUNTIME_TMP"
  export TEMP="$NODE_RUNTIME_TMP"
  export HOME="${NODE_RUNTIME_TMP}/home"
  export XDG_CACHE_HOME="${NODE_RUNTIME_TMP}/cache"
  export XDG_CONFIG_HOME="${NODE_RUNTIME_TMP}/config"
  mkdir -p "$HOME" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME"
  if [ ! -f "${NODE_RUNTIME_ROOT}/package.json" ] || ! cmp -s "${SKILL_ASSET_DIRECTORY}/package.json" "${NODE_RUNTIME_ROOT}/package.json" || [ ! -d "${NODE_RUNTIME_ROOT}/node_modules/playwright-core" ]; then
    cp "${SKILL_ASSET_DIRECTORY}/package.json" "${NODE_RUNTIME_ROOT}/package.json"
    echo "[stage] bun_install_start $(date +%s)" >&2
    if ! (cd "$NODE_RUNTIME_ROOT" && bun install --production); then
      return 1
    fi
    echo "[stage] bun_install_done $(date +%s)" >&2
  fi
  cp "$HTML_RENDER_SCRIPT" "${NODE_RUNTIME_ROOT}/html_render.mjs"
  HTML_RENDER_SCRIPT="${NODE_RUNTIME_ROOT}/html_render.mjs"
  export NODE_PATH="${NODE_RUNTIME_ROOT}/node_modules${NODE_PATH:+:$NODE_PATH}"
}

needs_node_environment() {
  local format_list=",${FORMATS},"
  case "$format_list" in
    *,all,*|*,pdf,*|*,pptx,*|*,review,*)
      return 0
      ;;
  esac
  return 1
}

if needs_node_environment; then
  if command -v bun &> /dev/null; then
    if ! ensure_node_environment; then
      echo "[warning] browser render environment is unavailable; continuing with fallback review/export" >&2
    fi
  else
    echo "[warning] bun is unavailable; continuing with fallback review/export" >&2
  fi
fi

mkdir -p "$BUILD_PATH"
export TMPDIR="${BUILD_PATH}/.tmp"
export TMP="$TMPDIR"
export TEMP="$TMPDIR"
export HOME="${TMPDIR}/home"
export XDG_CACHE_HOME="${TMPDIR}/cache"
export XDG_CONFIG_HOME="${TMPDIR}/config"
export XDG_RUNTIME_DIR="${TMPDIR}/runtime"
mkdir -p "$TMPDIR" "$HOME" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR" 2>/dev/null || true
rm -f "${BUILD_PATH}/${NAME}.html" "${BUILD_PATH}/${NAME}.pptx" "${BUILD_PATH}/${NAME}.pdf" "${BUILD_PATH}/${NAME}-notes.txt"

echo "Building requested formats: ${FORMATS}"
echo "[stage] build_formats_start $(date +%s)" >&2
if [ ! -f "$HTML_EXPORT_SCRIPT" ]; then
  echo "Error: html_export.py not found. Cannot export HTML-first deck." >&2
  exit 1
fi
PYTHONPATH="${SCRIPT_DIRECTORY}/..${PYTHONPATH:+:$PYTHONPATH}" python3 "$HTML_EXPORT_SCRIPT" "$SOURCE_PATH" "$NAME" "$BUILD_PATH" "$FORMATS" "$RENDER_REVIEW_SCRIPT" "$HTML_RENDER_SCRIPT"
echo "[stage] build_formats_done $(date +%s)" >&2
