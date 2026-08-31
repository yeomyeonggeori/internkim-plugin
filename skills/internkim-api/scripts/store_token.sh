#!/bin/sh
# Put an internkim API token in this computer's own secret store, and teach the
# shell to read it back into INTERNKIM_TOKEN.

set -eu

SERVICE="internkim"
ACCOUNT="api"

printf 'Paste the internkim API token (input is hidden): ' >&2
stty -echo 2>/dev/null || true
IFS= read -r TOKEN
stty echo 2>/dev/null || true
printf '\n' >&2

case "$TOKEN" in
	'') echo "no token given" >&2; exit 1 ;;
	ik_*) ;;
	*) echo "an internkim token starts with ik_" >&2; exit 1 ;;
esac

if command -v security >/dev/null 2>&1; then
	security add-generic-password -U -s "$SERVICE" -a "$ACCOUNT" -w "$TOKEN"
	READ_COMMAND="security find-generic-password -s $SERVICE -a $ACCOUNT -w"
elif command -v secret-tool >/dev/null 2>&1; then
	if ! printf '%s' "$TOKEN" | secret-tool store --label='internkim API token' service "$SERVICE" account "$ACCOUNT"; then
		echo "secret-tool could not reach a keyring. It needs a D-Bus session with an unlocked" >&2
		echo "keyring, which a headless machine has none of. Set INTERNKIM_TOKEN yourself there." >&2
		exit 1
	fi
	READ_COMMAND="secret-tool lookup service $SERVICE account $ACCOUNT"
else
	echo "no secret store found: this script knows macOS security and libsecret secret-tool" >&2
	echo "set INTERNKIM_TOKEN yourself, however this computer keeps secrets" >&2
	exit 1
fi

EXPORT_LINE="export INTERNKIM_TOKEN=\"\$($READ_COMMAND)\""

case "${SHELL##*/}" in
	zsh) PROFILE="${ZDOTDIR:-$HOME}/.zshrc" ;;
	bash) PROFILE="$HOME/.bashrc" ;;
	*) PROFILE="" ;;
esac

echo "Stored in this computer's secret store." >&2

if [ -z "$PROFILE" ]; then
	echo "Add this line wherever ${SHELL##*/} sets its environment:" >&2
	echo "  $EXPORT_LINE" >&2
	exit 0
fi

if [ -f "$PROFILE" ] && grep -q 'INTERNKIM_TOKEN' "$PROFILE"; then
	echo "$PROFILE already sets INTERNKIM_TOKEN, so it was left alone." >&2
	echo "  $EXPORT_LINE" >&2
	exit 0
fi

printf '\n# internkim API token, kept in this computer'"'"'s secret store\n%s\n' "$EXPORT_LINE" >> "$PROFILE"
echo "Added to $PROFILE. Open a new shell, or run:" >&2
echo "  $EXPORT_LINE" >&2
