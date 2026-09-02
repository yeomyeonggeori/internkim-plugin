#!/bin/bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIRECTORY="${SCRIPT_DIRECTORY}/../assets/scaffold"

if [ "$#" -ne 2 ]; then
	echo "usage: scaffold.sh <target-project-root> \"<site title>\"" >&2
	exit 2
fi

TARGET_PROJECT_ROOT="$1"
SITE_TITLE="$2"

if [ -z "$SITE_TITLE" ]; then
	echo "Error: the site title must not be empty." >&2
	exit 2
fi
if [ ! -d "$TEMPLATE_DIRECTORY/app" ]; then
	echo "Error: scaffold template missing at $TEMPLATE_DIRECTORY" >&2
	exit 1
fi
if [ -e "$TARGET_PROJECT_ROOT/app" ]; then
	echo "Error: $TARGET_PROJECT_ROOT/app already exists; this is an existing site project. Edit it in place instead of scaffolding again." >&2
	exit 1
fi

package_name_from_title() {
	local slug
	slug="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-60 | sed -E 's/-+$//')"
	if [ -z "$slug" ]; then
		slug="site"
	fi
	printf '%s' "$slug"
}

escape_title_for_html() {
	local escaped="$1"
	escaped="${escaped//&/&amp;}"
	escaped="${escaped//</&lt;}"
	escaped="${escaped//>/&gt;}"
	escaped="${escaped//\"/&\#34;}"
	escaped="${escaped//\'/&\#39;}"
	printf '%s' "$escaped"
}

PACKAGE_NAME="$(package_name_from_title "$SITE_TITLE")"
ESCAPED_TITLE="$(escape_title_for_html "$SITE_TITLE")"

mkdir -p "$TARGET_PROJECT_ROOT"
cp -R "$TEMPLATE_DIRECTORY/." "$TARGET_PROJECT_ROOT/"

substitute_placeholders() {
	local file_path="$1" content
	content="$(cat "$file_path")"
	content="${content//__SITE_PACKAGE_NAME__/$PACKAGE_NAME}"
	content="${content//__SITE_TITLE__/$ESCAPED_TITLE}"
	printf '%s\n' "$content" > "$file_path"
}

find "$TARGET_PROJECT_ROOT" -type f -print0 | while IFS= read -r -d '' template_file; do
	if grep -q "__SITE_PACKAGE_NAME__\|__SITE_TITLE__" "$template_file"; then
		substitute_placeholders "$template_file"
	fi
done

record_structural_manifest() {
	python3 - "$TARGET_PROJECT_ROOT" <<'PYEOF'
import hashlib, json, pathlib, sys

project_root = pathlib.Path(sys.argv[1])
app_directory = project_root / "app"
excluded_top_level = {"public", "dist", "node_modules"}
manifest = {}
for path in sorted(app_directory.rglob("*")):
    if not path.is_file():
        continue
    relative = path.relative_to(app_directory)
    if relative.parts[0] in excluded_top_level:
        continue
    manifest["app/" + "/".join(relative.parts)] = hashlib.sha256(path.read_bytes()).hexdigest()

state_directory = project_root / ".internkim"
state_directory.mkdir(parents=True, exist_ok=True)
manifest_path = state_directory / "scaffold-app-manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
PYEOF
}
record_structural_manifest

echo "Scaffolded site project at $TARGET_PROJECT_ROOT (title: $SITE_TITLE, package: $PACKAGE_NAME)."
echo "Next: fill app/public/site-content.json, rewrite DESIGN.md (remove the TODO(design) marker), then run validate.py. Content-only sites need no build; run build.sh only after changing app/src/**."
