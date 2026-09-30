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
    echo "bun is required for script-managed HTML-first slide export." >&2
    return 1
  fi
  if [ ! -f "${SKILL_ASSET_DIRECTORY}/package.json" ]; then
    echo "Slide export package manifest is missing: ${SKILL_ASSET_DIRECTORY}/package.json" >&2
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
    if ! (cd "$NODE_RUNTIME_ROOT" && bun install --production >&2); then
      return 1
    fi
    echo "[stage] bun_install_done $(date +%s)" >&2
  fi
  cp "$HTML_RENDER_SCRIPT" "${NODE_RUNTIME_ROOT}/html_render.mjs"
  cp "$(dirname "$HTML_RENDER_SCRIPT")/text_layout.mjs" "${NODE_RUNTIME_ROOT}/text_layout.mjs"
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

echo "[stage] build_formats_start $(date +%s)" >&2
PYTHONPATH="${SCRIPT_DIRECTORY}/..${PYTHONPATH:+:$PYTHONPATH}" python3 "$HTML_EXPORT_SCRIPT" "$SOURCE_PATH" "$NAME" "$BUILD_PATH" "$FORMATS" "$RENDER_REVIEW_SCRIPT" "$HTML_RENDER_SCRIPT"
echo "[stage] build_formats_done $(date +%s)" >&2
